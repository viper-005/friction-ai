"""Mock recovery workflows. Swap the print/log for real email/WhatsApp APIs later."""
from datetime import datetime

CHANNELS = {"email", "whatsapp", "sms", "support_ticket", "discount"}
LOG: list[dict] = []

TEMPLATES = {
    "payment_failure": "Your payment didn't go through. Here's a 1-click retry link + COD option.",
    "delivery_uncertainty": "Good news! Delivery to your pincode is available - arrives in 2-3 days.",
    "price_shock": "Free shipping unlocked for you: use code SHIPFREE on your saved cart.",
    "product_info_gap": "Still deciding? Here's a side-by-side comparison of your viewed products.",
    "post_purchase_issue": "We're sorry about the delay. Your order is prioritized; here's Rs 100 off next time.",
}


def trigger(session_id: str, customer_id: str, friction_type: str | None, channel: str, auto=False) -> dict:
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {sorted(CHANNELS)}")
    rec = dict(action_id=f"A{len(LOG)+1:04d}", session_id=session_id, customer_id=customer_id,
               friction_type=friction_type, channel=channel, auto_triggered=auto,
               message=TEMPLATES.get(friction_type, "We're here to help!"),
               status="sent (mock)", timestamp=datetime.now().isoformat(timespec="seconds"))
    LOG.append(rec)
    return rec
