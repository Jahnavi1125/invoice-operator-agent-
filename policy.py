import re
from memory import STATE, log

APPROVAL_LIMIT = 50000


def _is_submit(page, selector):
    try:
        return page.eval_on_selector(selector, "e => e.type === 'submit'")
    except Exception:
        return False


def check_click(page, selector):
    """Return a BLOCKED message if this click must not happen yet, else None."""
    if not _is_submit(page, selector):
        return None
    raw = page.eval_on_selector_all(
        "input[name='amount']", "els => els.length ? els[0].value : ''"
    )
    digits = re.sub(r"[^\d.]", "", raw or "")
    amount = float(digits) if digits else 0.0
    if amount > APPROVAL_LIMIT and not STATE["approved"]:
        msg = (
            f"BLOCKED BY POLICY: amount {amount:,.2f} is above the {APPROVAL_LIMIT:,} limit. "
            "You must call ask_human and get approval before clicking save."
        )
        log({"event": "policy_block", "amount": amount, "selector": selector})
        return msg
    STATE["approved"] = False
    return None