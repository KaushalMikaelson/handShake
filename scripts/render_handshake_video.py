"""Render the handShake demo middle segment as a screen-recording-style video.

The project environment does not ship ffmpeg, so this writes a simple MJPEG AVI
using only Pillow and the Python standard library.
"""
from __future__ import annotations

import math
import os
import struct
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "demo_video_assets"
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = ROOT / "handshake_demo_middle_4m20s.avi"
ARCH_IMAGE = Path(
    r"C:\Users\Kaushal\AppData\Local\Temp\codex-clipboard-05b10f5d-789b-43c0-96fe-418ade1d75e6.jpg"
)

W, H = 1280, 720
FPS = 8
DURATION = 260.0


COLORS = {
    "bg": "#f5f7fb",
    "ink": "#111827",
    "muted": "#64748b",
    "line": "#dbe3ef",
    "card": "#ffffff",
    "purple": "#5b4ce6",
    "purple2": "#8b5cf6",
    "green": "#02a67a",
    "green_bg": "#dff8ef",
    "amber": "#f59e0b",
    "amber_bg": "#fff6d8",
    "red": "#ef4444",
    "red_bg": "#fff0f0",
    "blue": "#2563eb",
    "blue_bg": "#e8f1ff",
    "dark": "#0f172a",
    "code": "#111827",
}


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    candidates = []
    if weight == "bold":
        candidates += [
            r"C:\Windows\Fonts\seguisb.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ]
    else:
        candidates += [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F = {
    "xs": font(15),
    "sm": font(18),
    "base": font(22),
    "md": font(26),
    "lg": font(34, "bold"),
    "xl": font(46, "bold"),
    "xxl": font(70, "bold"),
    "mono": ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 18)
    if Path(r"C:\Windows\Fonts\consola.ttf").exists()
    else font(18),
    "mono_sm": ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 15)
    if Path(r"C:\Windows\Fonts\consola.ttf").exists()
    else font(15),
}


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def rounded(draw: ImageDraw.ImageDraw, box, r, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def text(draw, xy, s, fill=None, fnt=None, anchor=None, spacing=4, align="left"):
    draw.text(xy, s, fill=fill or COLORS["ink"], font=fnt or F["base"], anchor=anchor, spacing=spacing, align=align)


def text_box(draw, box, s, fill=None, fnt=None, max_lines=None, line_gap=4):
    x1, y1, x2, _ = box
    fnt = fnt or F["base"]
    avg = max(7, fnt.getlength("n"))
    width_chars = max(8, int((x2 - x1) / avg))
    lines = []
    for para in s.split("\n"):
        lines.extend(textwrap.wrap(para, width=width_chars) or [""])
    if max_lines is not None:
        lines = lines[:max_lines]
    y = y1
    for line in lines:
        draw.text((x1, y), line, font=fnt, fill=fill or COLORS["ink"])
        y += fnt.size + line_gap
    return y


def shadow(base: Image.Image, box, r=14, alpha=35):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x1, y1 + 4, x2, y2 + 8), r, fill=(15, 23, 42, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(layer)


def card(img, box, title=None, subtitle=None):
    d = ImageDraw.Draw(img)
    shadow(img, box)
    rounded(d, box, 16, COLORS["card"], COLORS["line"])
    if title:
        text(d, (box[0] + 24, box[1] + 22), title, fnt=F["md"], fill=COLORS["ink"])
    if subtitle:
        text_box(d, (box[0] + 24, box[1] + 58, box[2] - 24, box[1] + 110), subtitle, fnt=F["sm"], fill=COLORS["muted"])


def browser_frame(title_s: str, url: str = "localhost:5174/buyer") -> Image.Image:
    img = Image.new("RGBA", (W, H), COLORS["bg"])
    d = ImageDraw.Draw(img)
    rounded(d, (38, 28, W - 38, H - 32), 18, "#eef2f8", "#d7deea")
    rounded(d, (38, 28, W - 38, 82), 18, "#e9eef6", "#d7deea")
    for i, c in enumerate(("#ef4444", "#f59e0b", "#22c55e")):
        d.ellipse((62 + i * 24, 47, 76 + i * 24, 61), fill=c)
    rounded(d, (160, 42, W - 260, 68), 8, "#ffffff", "#d7deea")
    text(d, (176, 47), url, fnt=F["xs"], fill=COLORS["muted"])
    text(d, (W - 235, 44), title_s, fnt=F["xs"], fill=COLORS["muted"])
    return img


def top_nav(draw, active="Buyer Agent", approval_count=4):
    rounded(draw, (60, 98, 260, 156), 14, "#ffffff", COLORS["line"])
    rounded(draw, (82, 113, 120, 143), 8, COLORS["purple"])
    text(draw, (132, 105), "handShake", fnt=F["base"], fill=COLORS["ink"])
    text(draw, (132, 130), "Bounded AI-to-AI Commerce", fnt=F["xs"], fill=COLORS["muted"])
    nav = [("Buyer Agent", 300), (f"Human Approvals {approval_count}", 470), ("Audit Trail", 690)]
    for label, x in nav:
        fill = "#edeaff" if active in label else "#ffffff"
        outline = COLORS["purple"] if active in label else COLORS["line"]
        rounded(draw, (x, 106, x + 150, 148), 11, fill, outline)
        text(draw, (x + 16, 117), label, fnt=F["xs"], fill=COLORS["purple"] if active in label else COLORS["muted"])
    rounded(draw, (930, 106, 1145, 148), 11, "#ffffff", COLORS["line"])
    text(draw, (948, 115), "Razorpay TEST | LLM Gemini", fnt=F["xs"], fill=COLORS["muted"])


def draw_dashboard(t: float) -> Image.Image:
    img = browser_frame("Buyer Dashboard")
    d = ImageDraw.Draw(img)
    top_nav(d, "Buyer Agent")
    card(img, (64, 184, 420, 636), "Agent status", "Acting for Aditi")
    text(d, (92, 260), "AUTONOMY LEVEL", fnt=F["xs"], fill=COLORS["muted"])
    for i, (label, detail) in enumerate([
        ("Recommend only", "Suggest, never buy"),
        ("Always ask me", "Approve every purchase"),
        ("Bounded auto-buy", "Buy small amounts alone"),
    ]):
        y = 290 + i * 64
        fill = "#eeeaff" if i == 2 else "#ffffff"
        outline = COLORS["purple"] if i == 2 else COLORS["line"]
        rounded(d, (92, y, 390, y + 48), 10, fill, outline, 2 if i == 2 else 1)
        text(d, (110, y + 8), label, fnt=F["sm"], fill=COLORS["ink"])
        text(d, (110, y + 30), detail, fnt=F["xs"], fill=COLORS["muted"])
    text(d, (92, 506), "Active policy", fnt=F["base"], fill=COLORS["ink"])
    for i, (k, v) in enumerate([
        ("Max per transaction", "₹2,00,000"),
        ("Ask above", "₹5,000"),
        ("Auto-buy below", "₹2,000"),
    ]):
        y = 542 + i * 30
        text(d, (104, y), k, fnt=F["xs"], fill=COLORS["muted"])
        text(d, (302, y), v, fnt=F["xs"], fill=COLORS["ink"])

    card(img, (456, 184, 1216, 636), "Shopping request", "Describe what you want to buy in natural language")
    rounded(d, (486, 262, 1186, 358), 12, "#ffffff", COLORS["line"])
    text(d, (512, 292), "Buy me boAt Rockerz 551ANC wireless headphones, budget Rs 4500", fnt=F["base"], fill=COLORS["ink"])
    rounded(d, (486, 384, 684, 436), 10, COLORS["purple"])
    text(d, (525, 398), "Run Buyer Agent", fnt=F["base"], fill="#ffffff")
    d.rectangle((718, 400, 738, 420), fill=COLORS["purple"])
    text(d, (748, 397), "Accept merchant bundle if offered", fnt=F["sm"], fill=COLORS["ink"])
    y = 484
    text(d, (486, y), "SCRIPTED DEMO PROMPTS", fnt=F["xs"], fill=COLORS["muted"])
    prompts = [("Auto-purchase with Bundle", "under ₹5,000"), ("Approval Gate with Bundle", "₹29,990"), ("Blocked by Policy", "over limit")]
    for i, (a, b) in enumerate(prompts):
        yy = y + 30 + i * 48
        rounded(d, (486, yy, 1186, yy + 38), 9, "#ffffff", COLORS["line"])
        text(d, (506, yy + 9), a, fnt=F["xs"], fill=COLORS["ink"])
        rounded(d, (1030, yy + 7, 1168, yy + 31), 8, "#ecfdf5" if i == 0 else "#fff7ed" if i == 1 else "#fff1f2")
        text(d, (1044, yy + 9), b, fnt=F["xs"], fill=COLORS["green"] if i == 0 else COLORS["amber"] if i == 1 else COLORS["red"])
    return img


def draw_input(t: float) -> Image.Image:
    img = draw_dashboard(t)
    d = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", img.size, (245, 247, 251, 170))
    img.alpha_composite(overlay)
    card(img, (180, 190, 1100, 510), "Natural Language Input", "The Buyer Agent receives a request. It can reason, but it cannot pay.")
    query = "Buy me noise-canceling headphones under ₹4,500"
    chars = int(lerp(0, len(query), ease(t)))
    rounded(d, (230, 310, 1050, 390), 12, "#ffffff", COLORS["purple"], 2)
    text(d, (258, 336), query[:chars], fnt=F["md"], fill=COLORS["ink"])
    if int(t * 8) % 2 == 0:
        x = 258 + F["md"].getlength(query[:chars])
        d.line((x, 332, x, 366), fill=COLORS["purple"], width=3)
    rounded(d, (230, 420, 470, 466), 10, COLORS["purple"])
    text(d, (270, 430), "Run Buyer Agent", fnt=F["sm"], fill="#ffffff")
    return img


def draw_candidates(t: float) -> Image.Image:
    img = browser_frame("Candidate Evaluation")
    d = ImageDraw.Draw(img)
    top_nav(d)
    card(img, (64, 120, 1216, 646), "Agent Recommendation", "Every candidate is evaluated against budget, stock, category, and fit.")
    cols = [90, 520, 690, 850, 1040]
    headers = ["Candidate", "Price", "Fit", "Reason", "Verdict"]
    for x, h in zip(cols, headers):
        text(d, (x, 210), h, fnt=F["xs"], fill=COLORS["muted"])
    rows = [
        ("Sony WH-CH720N", "₹8,999", "Noise cancelling", "Exceeds budget by ₹4,499", "Reject"),
        ("boAt Rockerz 551ANC", "₹3,499", "Wireless ANC", "Within budget, in stock, requested type", "Selected"),
        ("JBL Tune 760NC", "₹5,499", "ANC over-ear", "Exceeds budget by ₹999", "Reject"),
        ("Sennheiser HD 450BT", "₹11,999", "Premium ANC", "Exceeds budget by ₹7,499", "Reject"),
    ]
    reveal = int(lerp(0, len(rows), ease(t)))
    for i, row in enumerate(rows[:reveal]):
        y = 250 + i * 72
        selected = row[-1] == "Selected"
        rounded(d, (86, y - 14, 1168, y + 42), 10, COLORS["green_bg"] if selected else "#ffffff", COLORS["green"] if selected else COLORS["line"], 2 if selected else 1)
        for x, val in zip(cols, row):
            fill = COLORS["green"] if selected and val == "Selected" else COLORS["ink"]
            text(d, (x, y), val, fnt=F["sm"], fill=fill)
    if reveal == len(rows):
        rounded(d, (86, 560, 1168, 610), 10, "#f8fafc", COLORS["line"])
        text(d, (108, 573), "PurchaseIntent drafted: product_id=prod_boat_rockerz_551, amount sourced from catalog", fnt=F["sm"], fill=COLORS["ink"])
    return img


def draw_bundle(t: float) -> Image.Image:
    img = browser_frame("Merchant Bundle")
    d = ImageDraw.Draw(img)
    top_nav(d)
    card(img, (80, 150, 1200, 610), "Merchant Growth Agent", "The merchant can propose a bundle. It still cannot authorize payment.")
    rounded(d, (130, 255, 520, 410), 18, "#ffffff", COLORS["line"])
    text(d, (165, 285), "boAt Rockerz 551ANC", fnt=F["lg"], fill=COLORS["ink"])
    text(d, (165, 338), "Noise-canceling headphones", fnt=F["base"], fill=COLORS["muted"])
    text(d, (165, 372), "₹3,499", fnt=F["md"], fill=COLORS["ink"])
    text(d, (584, 326), "+", fnt=F["xxl"], fill=COLORS["purple"])
    rounded(d, (690, 255, 1080, 410), 18, "#ffffff", COLORS["line"])
    text(d, (725, 285), "Hardshell Carry Case", fnt=F["lg"], fill=COLORS["ink"])
    text(d, (725, 338), "Companion accessory", fnt=F["base"], fill=COLORS["muted"])
    text(d, (725, 372), "₹799", fnt=F["md"], fill=COLORS["ink"])
    rounded(d, (290, 472, 990, 548), 18, COLORS["amber_bg"], COLORS["amber"], 2)
    text(d, (330, 492), "Bundle offer: 8% off", fnt=F["md"], fill=COLORS["ink"])
    text(d, (680, 486), "₹4,298  →  ₹3,954.16", fnt=F["lg"], fill=COLORS["amber"])
    return img


def draw_policy(t: float) -> Image.Image:
    img = browser_frame("Policy Verdict")
    d = ImageDraw.Draw(img)
    top_nav(d, approval_count=4)
    card(img, (64, 112, 1216, 650), "Policy Engine Verdict", "Deterministic evaluation. Zero LLM. Zero network. Razorpay is not called.")
    rounded(d, (96, 202, 560, 310), 16, COLORS["amber_bg"], COLORS["amber"], 3)
    text(d, (128, 232), "REQUIRES_APPROVAL", fnt=F["lg"], fill=COLORS["amber"])
    text(d, (130, 276), "Final amount: ₹3,954.16", fnt=F["base"], fill=COLORS["ink"])
    checks = [
        ("category.blocked", "PASS", "electronics is not blocked"),
        ("category.allowed", "PASS", "electronics is explicitly allowed"),
        ("budget.max_transaction", "PASS", "within ₹2,00,000 cap"),
        ("budget.daily", "PASS", "within daily budget"),
        ("merchant.bundle_price_integrity", "PASS", "₹3,954.16 matches 8% off ₹4,298"),
    ]
    for i, (rule, status, detail) in enumerate(checks):
        y = 350 + i * 46
        rounded(d, (96, y - 10, 780, y + 28), 8, "#ffffff", COLORS["line"])
        text(d, (116, y), f"{i + 1}. {status}", fnt=F["xs"], fill=COLORS["green"])
        text(d, (220, y), rule, fnt=F["xs"], fill=COLORS["ink"])
        text(d, (490, y), detail, fnt=F["xs"], fill=COLORS["muted"])
    rounded(d, (840, 220, 1160, 530), 18, "#fff7ed", COLORS["amber"], 2)
    text_box(d, (870, 250, 1130, 420), "₹3,954.16 sits between the auto-purchase ceiling (₹2,000) and the approval threshold (₹5,000). The safe default in that band is to ask.", fnt=F["base"], fill=COLORS["ink"])
    rounded(d, (884, 466, 1118, 506), 10, COLORS["red_bg"], COLORS["red"])
    text(d, (920, 475), "Razorpay called: FALSE", fnt=F["sm"], fill=COLORS["red"])
    return img


def draw_approvals(t: float) -> Image.Image:
    img = browser_frame("Approvals")
    d = ImageDraw.Draw(img)
    top_nav(d, "Human Approvals", approval_count=4)
    card(img, (70, 118, 1210, 650), "Human Approval Dashboard", "The user sees the purchase details and why approval is required.")
    rounded(d, (112, 224, 1168, 390), 14, "#ffffff", COLORS["line"])
    text(d, (144, 254), "boAt Rockerz 551ANC + Universal Hardshell Case", fnt=F["lg"], fill=COLORS["ink"])
    text(d, (144, 306), "Amount: ₹3,954.16    Reason: above autonomous ceiling, below approval threshold", fnt=F["base"], fill=COLORS["muted"])
    text(d, (144, 344), "Intent: pi_497cf7ff1b8c428d    Merchant: AudioHub India", fnt=F["sm"], fill=COLORS["muted"])
    if t < 0.55:
        rounded(d, (144, 460, 396, 526), 12, COLORS["green"])
        text(d, (192, 480), "Approve & Execute", fnt=F["md"], fill="#ffffff")
        rounded(d, (430, 460, 650, 526), 12, "#ffffff", COLORS["red"], 2)
        text(d, (485, 480), "Reject", fnt=F["md"], fill=COLORS["red"])
    else:
        rounded(d, (144, 460, 500, 526), 12, COLORS["green_bg"], COLORS["green"], 2)
        text(d, (184, 480), "APPROVED BY HUMAN", fnt=F["md"], fill=COLORS["green"])
        x = lerp(270, 450, ease((t - 0.55) / 0.45))
        d.ellipse((x - 16, 444, x + 16, 476), fill="#ffffff", outline=COLORS["green"], width=3)
    return img


def draw_razorpay(t: float) -> Image.Image:
    img = browser_frame("Razorpay Test Mode")
    d = ImageDraw.Draw(img)
    top_nav(d, "Audit Trail", approval_count=3)
    card(img, (76, 128, 1204, 642), "Financial Execution Path", "Only after approval does the backend create a Razorpay test-mode order.")
    steps = [
        ("Human approval granted", COLORS["green"]),
        ("Razorpay order created", COLORS["blue"]),
        ("Webhook signature verified", COLORS["blue"]),
        ("Transaction recorded", COLORS["green"]),
        ("Audit trail appended", COLORS["green"]),
    ]
    for i, (label, color) in enumerate(steps):
        x = 130 + i * 220
        y = 332
        d.line((x + 70, y, x + 205, y), fill=COLORS["line"], width=4)
        d.ellipse((x, y - 34, x + 68, y + 34), fill="#ffffff", outline=color, width=4)
        text(d, (x + 34, y - 14), str(i + 1), fnt=F["md"], fill=color, anchor="ma")
        text_box(d, (x - 28, y + 56, x + 130, y + 124), label, fnt=F["sm"], fill=COLORS["ink"])
    rounded(d, (322, 184, 958, 250), 12, COLORS["blue_bg"], COLORS["blue"], 2)
    text(d, (372, 204), "Order: order_TYG... | idempotency: intent_pi_497cf7ff1b8c428d", fnt=F["base"], fill=COLORS["blue"])
    text_box(d, (280, 520, 1000, 590), "The important part is not simply that payment can succeed. It is that the AI never had authority to execute it by itself.", fnt=F["md"], fill=COLORS["ink"])
    return img


def draw_architecture(t: float, zoom=False, callouts=False) -> Image.Image:
    img = Image.new("RGBA", (W, H), "#f3f4f6")
    d = ImageDraw.Draw(img)
    if ARCH_IMAGE.exists():
        arch = Image.open(ARCH_IMAGE).convert("RGB")
    else:
        arch = Image.new("RGB", (720, 1200), "#ffffff")
    if zoom:
        # Focus on the AI-to-policy boundary.
        crop = arch.crop((90, 360, arch.width - 70, 1450))
    else:
        crop = arch.crop((70, 320, arch.width - 55, 1780))
    crop.thumbnail((640 if not zoom else 760, 650), Image.Resampling.LANCZOS)
    x = 72 if not zoom else 58
    y = (H - crop.height) // 2
    rounded(d, (x - 18, y - 18, x + crop.width + 18, y + crop.height + 18), 18, "#ffffff", COLORS["line"])
    img.paste(crop, (x, y))
    card(img, (735, 110, 1198, 612), "Architecture", "User → Buyer Agent → Merchant Agent → Policy Engine → Approval or Autonomous Purchase → Razorpay → Audit Trail")
    items = [
        ("LLM stops at PurchaseIntent", COLORS["purple"]),
        ("Policy Engine is deterministic Python", COLORS["green"]),
        ("Razorpay never receives blocked or unapproved intents", COLORS["red"]),
        ("Every outcome lands in the audit trail", COLORS["blue"]),
    ]
    for i, (label, color) in enumerate(items):
        yy = 250 + i * 72
        d.ellipse((770, yy, 792, yy + 22), fill=color)
        text_box(d, (812, yy - 4, 1158, yy + 44), label, fnt=F["base"], fill=COLORS["ink"])
    if callouts:
        rounded(d, (132, 225, 548, 284), 12, "#fff7ed", COLORS["amber"], 3)
        text(d, (160, 240), "AI reasoning boundary", fnt=F["md"], fill=COLORS["amber"])
        rounded(d, (108, 390, 586, 454), 12, "#ecfdf5", COLORS["green"], 3)
        text(d, (130, 410), "Deterministic policy starts here", fnt=F["md"], fill=COLORS["green"])
    return img


def read_snippet(path: str, start: int, end: int) -> list[str]:
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    return [f"{i + 1:>3}  {lines[i]}" for i in range(start - 1, min(end, len(lines)))]


def draw_code(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), COLORS["code"])
    d = ImageDraw.Draw(img)
    rounded(d, (34, 28, 1246, 692), 16, "#0b1220", "#273449")
    text(d, (72, 58), "VS Code - handShake", fnt=F["md"], fill="#e5e7eb")
    files = [
        ("backend/app/services/orchestrator.py", 250, 319),
        ("backend/app/policies/approval.py", 28, 56),
        ("backend/app/payments/webhook.py", 56, 128),
    ]
    idx = min(2, int(t * 3))
    path, start, end = files[idx]
    rounded(d, (58, 100, 430, 650), 10, "#101827", "#273449")
    for i, name in enumerate(["orchestrator.py", "approval.py", "razorpay_service.py", "webhook.py", "test_architecture.py"]):
        yy = 132 + i * 42
        fill = "#1f2a44" if name in path else "#101827"
        rounded(d, (78, yy - 8, 400, yy + 24), 6, fill)
        text(d, (94, yy - 2), name, fnt=F["xs"], fill="#cbd5e1")
    rounded(d, (456, 100, 1218, 650), 10, "#0f172a", "#273449")
    text(d, (480, 124), path, fnt=F["sm"], fill="#93c5fd")
    snippet = read_snippet(path, start, end)
    y = 166
    for line in snippet[:24]:
        fill = "#cbd5e1"
        if "execute_payment" in line or "Razorpay" in line or "requires_human_approval" in line:
            fill = "#fbbf24"
        if "verify_webhook_signature" in line or "IntegrityError" in line or "raw" in line.lower():
            fill = "#34d399"
        text(d, (482, y), line.expandtabs(4), fnt=F["mono_sm"], fill=fill)
        y += 19
    rounded(d, (480, 590, 1190, 626), 8, "#172554", "#2563eb")
    captions = [
        "Agents create PurchaseIntent; policy gates the payment path.",
        "The route_authority function chooses auto-buy vs human approval.",
        "Webhook safety: verify signature, claim event ID, apply side effect once.",
    ]
    text(d, (500, 598), captions[idx], fnt=F["sm"], fill="#dbeafe")
    return img


def draw_failure(t: float) -> Image.Image:
    img = browser_frame("Failure Drill")
    d = ImageDraw.Draw(img)
    top_nav(d, "Audit Trail", approval_count=3)
    card(img, (64, 118, 1216, 646), "Failure Drills", "Financial systems are judged by what happens when things go wrong.")
    drills = [
        ("Policy violation", "BLOCKED before Razorpay", COLORS["red"], "0 gateway calls"),
        ("Duplicate webhook", "duplicate_ignored", COLORS["amber"], "spend committed once"),
        ("Payment timeout", "PENDING_VERIFICATION", COLORS["blue"], "verify, never blind retry"),
        ("Forged signature", "invalid_signature", COLORS["red"], "rejected before parsing"),
    ]
    reveal = min(4, max(1, math.ceil(lerp(1, 4, ease(t)))))
    for i, (name, status, color, detail) in enumerate(drills[:reveal]):
        x = 100 + (i % 2) * 555
        y = 230 + (i // 2) * 170
        rounded(d, (x, y, x + 500, y + 120), 16, "#ffffff", color, 2)
        text(d, (x + 28, y + 26), name, fnt=F["lg"], fill=COLORS["ink"])
        text(d, (x + 28, y + 68), status, fnt=F["base"], fill=color)
        text(d, (x + 300, y + 70), detail, fnt=F["sm"], fill=COLORS["muted"])
    rounded(d, (250, 560, 1030, 622), 14, "#f8fafc", COLORS["line"])
    text(d, (640, 574), "AI controls intent. Software controls money.", fnt=F["md"], fill=COLORS["ink"], anchor="ma")
    return img


def draw_title(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), COLORS["dark"])
    d = ImageDraw.Draw(img)
    for i in range(9):
        x = int((i * 170 + t * 45) % W)
        d.line((x, 0, x - 240, H), fill=(30, 41, 59, 90), width=2)
    rounded(d, (500, 178, 780, 242), 18, COLORS["purple"])
    text(d, (640, 188), "handShake", fnt=F["lg"], fill="#ffffff", anchor="ma")
    text(d, (640, 282), "Bounded AI-to-AI Commerce", fnt=F["xl"], fill="#ffffff", anchor="ma")
    text_box(d, (250, 358, 1030, 460), "AI agents reason about products. Deterministic software controls financial execution on Razorpay.", fnt=F["md"], fill="#cbd5e1", max_lines=3)
    rounded(d, (410, 520, 870, 580), 14, "#172554", "#2563eb")
    text(d, (640, 535), "AI controls intent. Software controls money.", fnt=F["md"], fill="#dbeafe", anchor="ma")
    return img


@dataclass
class Scene:
    start: float
    end: float
    name: str
    fn: callable


SCENES = [
    Scene(0, 15, "TITLE / HANDSHAKE", draw_title),
    Scene(15, 35, "BUYER DASHBOARD", lambda t: draw_dashboard(t)),
    Scene(35, 50, "NATURAL LANGUAGE INPUT", draw_input),
    Scene(50, 70, "CANDIDATE EVALUATION", draw_candidates),
    Scene(70, 85, "MERCHANT BUNDLE", draw_bundle),
    Scene(85, 105, "POLICY VERDICT", draw_policy),
    Scene(105, 120, "APPROVALS", draw_approvals),
    Scene(120, 130, "RAZORPAY / SUCCESS", draw_razorpay),
    Scene(130, 135, "HARD CUT", lambda t: Image.new("RGBA", (W, H), "#020617")),
    Scene(135, 180, "ARCHITECTURE", lambda t: draw_architecture(t)),
    Scene(180, 190, "ZOOM -> LLM BOUNDARY", lambda t: draw_architecture(t, zoom=True, callouts=True)),
    Scene(190, 200, "VS CODE", draw_code),
    Scene(200, 230, "ARCHITECTURE", lambda t: draw_architecture(t, callouts=True)),
    Scene(230, 260, "FAILURE DRILL", draw_failure),
]


def scene_at(ts: float) -> tuple[Scene, float]:
    for s in SCENES:
        if s.start <= ts < s.end:
            return s, (ts - s.start) / (s.end - s.start)
    s = SCENES[-1]
    return s, 1.0


def add_timeline(img: Image.Image, ts: float, scene_name: str):
    d = ImageDraw.Draw(img)
    # This video is the middle segment. The user's camera intro occupies 00:00-00:20,
    # so the visible guide uses the absolute timeline from the full cut.
    elapsed = int(ts + 20)
    mins, secs = divmod(elapsed, 60)
    rounded(d, (26, H - 34, W - 26, H - 12), 8, (255, 255, 255, 210))
    d.rectangle((38, H - 26, W - 38, H - 22), fill="#dbe3ef")
    d.rectangle((38, H - 26, 38 + int((W - 76) * ts / DURATION), H - 22), fill=COLORS["purple"])
    text(d, (48, H - 54), f"{mins:02d}:{secs:02d}  {scene_name}", fnt=F["xs"], fill=COLORS["muted"])


class AviWriter:
    def __init__(self, path: Path, width: int, height: int, fps: int):
        self.f = path.open("wb")
        self.w = width
        self.h = height
        self.fps = fps
        self.frames = 0
        self.index: list[tuple[int, int]] = []
        self._write_header_placeholder()

    def _chunk(self, fourcc: bytes, payload: bytes):
        self.f.write(fourcc)
        self.f.write(struct.pack("<I", len(payload)))
        self.f.write(payload)
        if len(payload) & 1:
            self.f.write(b"\0")

    def _list_start(self, kind: bytes) -> int:
        self.f.write(b"LIST")
        pos = self.f.tell()
        self.f.write(b"\0\0\0\0")
        self.f.write(kind)
        return pos

    def _list_end(self, pos: int):
        cur = self.f.tell()
        self.f.seek(pos)
        self.f.write(struct.pack("<I", cur - pos - 4))
        self.f.seek(cur)

    def _write_header_placeholder(self):
        self.f.write(b"RIFF")
        self.riff_size_pos = self.f.tell()
        self.f.write(b"\0\0\0\0AVI ")
        hdrl = self._list_start(b"hdrl")
        avih = struct.pack(
            "<IIIIIIIIII4I",
            int(1_000_000 / self.fps),
            self.w * self.h * 3 * self.fps,
            0,
            0x10,
            0,
            0,
            1,
            self.w * self.h * 3,
            self.w,
            self.h,
            0,
            0,
            0,
            0,
        )
        self.avih_frames_pos = self.f.tell() + 8 + 16
        self._chunk(b"avih", avih)
        strl = self._list_start(b"strl")
        strh = struct.pack(
            "<4s4sIIIIIIIIIIIIhhhh",
            b"vids",
            b"MJPG",
            0,
            0,
            0,
            0,
            1,
            self.fps,
            0,
            0,
            self.w * self.h * 3,
            0xFFFFFFFF,
            0,
            self.w * self.h * 3,
            0,
            0,
            self.w,
            self.h,
        )
        self.strh_frames_pos = self.f.tell() + 8 + 32
        self._chunk(b"strh", strh)
        strf = struct.pack("<IiiHH4sIiiII", 40, self.w, self.h, 1, 24, b"MJPG", self.w * self.h * 3, 0, 0, 0, 0)
        self._chunk(b"strf", strf)
        self._list_end(strl)
        self._list_end(hdrl)
        self.movi_list_pos = self._list_start(b"movi")
        self.movi_data_start = self.f.tell()

    def add(self, img: Image.Image):
        import io

        rgb = img.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=72, optimize=False)
        payload = buf.getvalue()
        offset = self.f.tell() - self.movi_data_start
        self._chunk(b"00dc", payload)
        self.index.append((offset, len(payload)))
        self.frames += 1

    def close(self):
        self._list_end(self.movi_list_pos)
        idx_payload = bytearray()
        for offset, size in self.index:
            idx_payload += struct.pack("<4sIII", b"00dc", 0x10, offset, size)
        self._chunk(b"idx1", bytes(idx_payload))
        end = self.f.tell()
        self.f.seek(self.riff_size_pos)
        self.f.write(struct.pack("<I", end - 8))
        self.f.seek(self.avih_frames_pos)
        self.f.write(struct.pack("<I", self.frames))
        self.f.seek(self.strh_frames_pos)
        self.f.write(struct.pack("<I", self.frames))
        self.f.close()


def main():
    writer = AviWriter(OUT_FILE, W, H, FPS)
    total = int(DURATION * FPS)
    for i in range(total):
        ts = i / FPS
        scene, local = scene_at(ts)
        frame = scene.fn(local)
        add_timeline(frame, ts, scene.name)
        writer.add(frame)
        if i % (FPS * 10) == 0:
            print(f"rendered {int(ts):>3}s / {int(DURATION)}s")
    writer.close()
    print(f"wrote {OUT_FILE}")
    print(f"size {OUT_FILE.stat().st_size / (1024 * 1024):.1f} MB")


if __name__ == "__main__":
    main()
