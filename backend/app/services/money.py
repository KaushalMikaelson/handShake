"""Money helpers.

Decision (PRD 5.7 Q1): paise, everywhere, as Python ints. Razorpay's API expects
paise, so storing rupees anywhere would introduce a conversion point - and a
100x bug waiting to happen. Rupee strings exist only for display.
"""


def rupees(paise: int) -> int:
    """Whole rupees, truncated - display only, never used for charging."""
    return paise // 100


def to_paise(rupee_amount: float | int) -> int:
    """Convert a rupee figure (e.g. parsed from user text) to integer paise."""
    return int(round(float(rupee_amount) * 100))


def format_inr(paise: int) -> str:
    """Render paise as an Indian-format rupee string, e.g. 899900 -> 'Rs 8,999'."""
    whole, frac = divmod(int(paise), 100)
    sign = "-" if whole < 0 or paise < 0 else ""
    whole = abs(whole)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    out = f"{sign}Rs {s}"
    if frac:
        out += f".{frac:02d}"
    return out
