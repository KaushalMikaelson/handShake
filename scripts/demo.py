#!/usr/bin/env python3
"""Drive the full 5-minute demo (PRD section 6) against a running API.

    python scripts/demo.py [--base-url http://127.0.0.1:8000]

Runs the exact beats in order and prints what a judge needs to see: the
decision, the rule that fired, whether Razorpay was called, and the audit
trail. Scripted rather than typed (PRD 5.7 Q4) so every failure-mode beat
triggers reliably.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, RED, YELLOW, BLUE = "\033[32m", "\033[31m", "\033[33m", "\033[34m"


def call(base: str, path: str, payload: dict | None = None) -> dict:
    url = f"{base}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def rupees(paise) -> str:
    return "—" if paise is None else f"₹{paise / 100:,.2f}".replace(".00", "")


def beat(n: str, title: str) -> None:
    print(f"\n{BOLD}{BLUE}── {n} · {title} {'─' * max(0, 58 - len(title))}{RESET}")


def verdict(ok: bool, text: str) -> None:
    print(f"  {GREEN + '✓' if ok else RED + '✗'} {text}{RESET}")


def show_flow(r: dict) -> None:
    if r.get("recommendation") and r["recommendation"].get("selected_name"):
        rec = r["recommendation"]
        print(f"  {DIM}buyer agent  :{RESET} {rec['selected_name']} @ {rupees(rec['amount'])}")
        print(f"  {DIM}reasoning    :{RESET} {rec['justification'][:110]}")
    if r.get("bundle"):
        b = r["bundle"]
        label = (f"bundle at {b['discount_pct']}% off → {rupees(b['bundle_price'])}"
                 if b["offered"] else "no_bundle_offered")
        print(f"  {DIM}growth agent :{RESET} {label}")
    if r.get("policy"):
        p = r["policy"]
        colour = RED if p["decision"] == "BLOCKED" else GREEN
        print(f"  {DIM}policy       :{RESET} {colour}{p['decision']}{RESET} — {p['reason'][:95]}")
        if p["failed_rule"]:
            print(f"  {DIM}failed rule  :{RESET} {RED}{p['failed_rule']}{RESET}")
    if r.get("trust"):
        print(f"  {DIM}trust        :{RESET} {r['trust']['score']}/100 ({r['trust']['band']}) — advisory only")
    if r.get("transaction"):
        t = r["transaction"]
        print(f"  {DIM}transaction  :{RESET} {t['status']} · {t['razorpay_order_id']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    try:
        status = call(base, "/system/status")
    except Exception as exc:
        print(f"{RED}Cannot reach the API at {base}: {exc}{RESET}")
        print("Start it with:  ./scripts/dev.sh   (or docker compose up)")
        return 1

    print(f"{BOLD}Bounded AI-to-AI Commerce — demo script{RESET}")
    print(f"{DIM}payments: {status['payments']['mode']} · llm: {status['llm']['mode']}{RESET}")

    # ---------------------------------------------------------------- 0:30
    beat("1", "Happy path — bounded auto-purchase")
    r = call(base, "/buyer/shop",
             {"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"})
    show_flow(r)
    verdict(r["status"] == "completed", f"auto-purchased without asking: {r['message']}")
    happy_intent = (r.get("intent") or {}).get("intent_id")

    # ---------------------------------------------------------------- 1:30
    beat("2", "Approval gate — above the ₹5,000 threshold")
    r = call(base, "/buyer/shop",
             {"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"})
    show_flow(r)
    verdict(r["status"] == "awaiting_approval", "routed to a human instead of paying")
    verdict(not r["razorpay_called"], "Razorpay NOT called while awaiting approval")

    approval_id = r["approval"]["approval_id"]
    print(f"  {DIM}…human presses Approve{RESET}")
    r = call(base, f"/approvals/{approval_id}/decision", {"decision": "approve", "actor": "aditi"})
    show_flow(r)
    verdict(r["status"] == "completed", f"paid after approval: {r['message']}")

    # ---------------------------------------------------------------- 2:30
    beat("3", "Blocked purchase — trust never overrides budget")
    r = call(base, "/drills/policy-violation", {})
    show_flow(r)
    verdict(r["status"] == "blocked", f"blocked by rule '{r['policy']['failed_rule']}'")
    verdict(not r["razorpay_called"], "Razorpay was NEVER called on the blocked path")
    verdict(r["trust"]["score"] == 100,
            "a 100/100-trust merchant was still blocked — trust is advisory only")

    # ---------------------------------------------------------------- 3:15
    beat("4", "Failure recovery — payment timeout")
    r = call(base, "/drills/payment-timeout", {})
    show_flow(r)
    verdict(r["status"] == "pending_verification",
            "held as PENDING_VERIFICATION and resolved by asking the gateway — no blind retry")

    beat("5", "Failure recovery — duplicate webhook")
    r = call(base, "/drills/duplicate-webhook", {})
    print(f"  {DIM}first  :{RESET} {r['first_delivery']['status']}")
    print(f"  {DIM}second :{RESET} {r['second_delivery']['status']}")
    verdict(r["second_delivery"]["duplicate"], "replay detected and ignored — no double-charge")

    beat("6", "Failure recovery — forged webhook signature")
    r = call(base, "/drills/tampered-webhook", {})
    verdict(not r["accepted"], f"rejected: {r['detail']}")

    # ---------------------------------------------------------------- 4:15
    beat("7", "Full audit trail for one transaction")
    if happy_intent:
        timeline = call(base, f"/audit/timeline/{happy_intent}")
        for e in timeline["events"]:
            print(f"  {DIM}{e['sequence']:>2}{RESET} {e['agent_id']:<17} "
                  f"{BOLD}{e['action']:<24}{RESET} {e['reason'][:72]}")
        verdict(timeline["event_count"] >= 10,
                f"{timeline['event_count']} events recorded, every one timestamped and explained")

    state = call(base, "/buyer/state")
    print(f"\n  {DIM}budget:{RESET} {rupees(state['spent_today'])} spent today · "
          f"{rupees(state['remaining_today'])} remaining")

    print(f"\n{BOLD}We didn't build an AI that can spend money —{RESET}")
    print(f"{BOLD}we built an AI that can spend money only within rules its owner controls.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
