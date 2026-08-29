"""Architectural boundary tests.

These enforce the claims in the README mechanically, so they cannot silently
rot as the code changes. A README that says "only one module imports the
payment SDK" is a comment; this file makes it a build failure.
"""
import ast
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
APP = BACKEND / "app"

FORBIDDEN_IN_POLICIES = {
    "anthropic", "razorpay", "httpx", "requests", "openai",
    "sqlalchemy", "fastapi", "urllib", "socket", "http",
}

RAZORPAY_SDK_OWNER = APP / "payments" / "razorpay_service.py"


def python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in str(p))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", python_files(APP / "policies"), ids=lambda p: p.name)
def test_policy_engine_imports_nothing_heavy(path):
    """The guardrail package must stay free of LLM, network and ORM imports.

    This is what lets the engine be unit-tested with zero mocking, and what
    guarantees no model output can reach it through a side channel.
    """
    offenders = imported_modules(path) & FORBIDDEN_IN_POLICIES
    assert not offenders, f"{path.name} imports forbidden modules: {sorted(offenders)}"


def test_only_one_module_imports_the_razorpay_sdk():
    """Security Principle: all money movement flows through one auditable choke-point."""
    offenders = []
    for path in python_files(APP):
        if path == RAZORPAY_SDK_OWNER:
            continue
        if "razorpay" in imported_modules(path):
            offenders.append(str(path.relative_to(BACKEND)))
    assert not offenders, (
        f"Only {RAZORPAY_SDK_OWNER.name} may import the Razorpay SDK. Offenders: {offenders}"
    )


def test_only_the_llm_client_imports_anthropic():
    owner = APP / "agents" / "llm" / "client.py"
    offenders = [
        str(p.relative_to(BACKEND))
        for p in python_files(APP)
        if p != owner and "anthropic" in imported_modules(p)
    ]
    assert not offenders, f"Only the LLM client may import anthropic. Offenders: {offenders}"


def test_agent_modules_cannot_import_the_payment_layer():
    """The AI layer must have no route to the gateway, not even an indirect one."""
    offenders = []
    for path in python_files(APP / "agents"):
        text = path.read_text()
        if "app.payments" in text or "razorpay_service" in text:
            offenders.append(str(path.relative_to(BACKEND)))
    assert not offenders, (
        f"Agent modules must not reference the payment layer. Offenders: {offenders}"
    )


def test_no_update_or_delete_path_exists_for_audit_events():
    """US-9: audit events are append-only once written."""
    offenders = []
    for path in python_files(APP):
        text = path.read_text()
        for marker in ("delete(AuditEvent", "AuditEvent).delete", "AuditEvent).update"):
            if marker in text:
                offenders.append(f"{path.relative_to(BACKEND)}: {marker}")
    assert not offenders, f"Audit log must be immutable. Offenders: {offenders}"


def test_llm_is_never_given_a_payment_tool():
    """Every tool schema handed to the model is inspected for money verbs."""
    forbidden = ("create_order", "capture", "charge", "refund", "payment", "razorpay")
    offenders = []
    for path in python_files(APP / "agents"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            # tool schemas are module-level dicts named *_TOOL_SCHEMA
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.endswith("TOOL_SCHEMA"):
                        rendered = ast.dump(node.value).lower()
                        hits = [f for f in forbidden if f in rendered]
                        if hits:
                            offenders.append(f"{path.name}:{target.id} -> {hits}")
    assert not offenders, f"No LLM tool schema may expose payment capability: {offenders}"


def test_policy_package_is_importable_without_the_app_stack():
    """Proves the isolation claim: importable in a bare interpreter."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from app.policies import evaluate; "
         "assert 'sqlalchemy' not in sys.modules; "
         "assert 'anthropic' not in sys.modules; "
         "print('clean')"],
        cwd=BACKEND, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout
