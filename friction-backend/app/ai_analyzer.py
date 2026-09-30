"""
Journey Friction Detection & Recovery Assistant  (Member 3 - AI/ML)  -- v2

PIPELINE (each step is its own function, read them top to bottom):

  raw session
    -> clean_session()          preprocessing: dedupe, missing values, timestamps, feedback text
    -> analyze_feedback()       sentiment / themes / severity  (rules; optional LLM)
    -> engineer_features()      numeric, ML-ready features
    -> analyze_journey()        stage timeline + "what happened right before exit"
    -> detect_causes()          7 rule-based detectors -> scores + structured evidence
    -> select_causes()          primary + secondary cause, with a written reason
    -> calculate_confidence()   rule-based confidence + factors
    -> calculate_risk()         rule-based risk score + factors
    -> build_recommendation()   contextual recovery action
    -> build_business_action()  workflow trigger for the business team
    -> record_outcome()         feedback loop: did the recovery work?

IMPORTANT HONESTY NOTE
  * Every score here is a RULE-BASED HEURISTIC written by hand.
  * "confidence" and "risk_score" are NOT statistically validated probabilities.
  * Nothing has been trained or validated on real customer data.

INPUT (one session):
{
  "session_id": "S1", "customer_id": "C1",
  "events": [ {"type": "product_view", "ts": 0, "meta": {...}}, ... ],
  "feedback": "optional review / chat / ticket text"
}
"ts" can be seconds (0, 40, 125...), epoch seconds/milliseconds, or an ISO string.
Event types: page_view, search, product_view, compare, review_read, size_chart_view,
  add_to_cart, remove_from_cart, view_cart, delivery_check, shipping_cost_shown,
  coupon_failed, checkout_start, form_error, payment_attempt, payment_failed,
  purchase, support_chat, support_ticket, order_delayed, session_exit
Useful meta keys: category, price, shipping_cost, delivery_days, faster_option

Run demo:  python ai_analyzer.py
Run API :  pip install -r requirements.txt ; uvicorn ai_analyzer:app --reload
Run tests: python -m unittest -v
"""
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# =====================================================================
# 1. CONSTANTS  (PLAYBOOK, KEYWORDS and DETECTORS keys are kept from v1)
# =====================================================================
PLAYBOOK = {
    "PAYMENT_FAILURE": {
        "label": "Payment failure",
        "action": "Send a payment-retry link with an alternate method (UPI/COD/wallet) and notify the payments team.",
        "channel": "SMS / WhatsApp + push", "owner": "Payments / Ops", "urgency": "HIGH",
        "message": "Your payment didn't go through - your cart is saved! Retry in one tap or pay via UPI / Cash on Delivery.",
    },
    "DELIVERY_UNCERTAINTY": {
        "label": "Delivery uncertainty",
        "action": "Show guaranteed delivery date on product/cart page and send a delivery-date reassurance message.",
        "channel": "Email + in-app banner", "owner": "Logistics / Product", "urgency": "MEDIUM",
        "message": "Good news - your items can reach you {eta}. Free returns if it's late!",
    },
    "UNCLEAR_PRODUCT_INFO": {
        "label": "Unclear product information",
        "action": "Trigger a chatbot/assistant offer with specs, size guide and top reviews; improve product page content.",
        "channel": "In-app chat / email", "owner": "Product / Catalog", "urgency": "MEDIUM",
        "message": "Not sure about this product? Here's a quick size guide, key specs and what buyers say.",
    },
    "PRICE_SHOCK": {
        "label": "Hidden cost / price shock",
        "action": "Offer a targeted coupon or free-shipping threshold nudge; show total price earlier in the journey.",
        "channel": "Email + push", "owner": "Marketing / Pricing", "urgency": "MEDIUM",
        "message": "Here's 10% off + free shipping on your saved cart - valid for 24 hours.",
    },
    "POOR_RECOMMENDATIONS": {
        "label": "Poor recommendations / choice overload",
        "action": "Send personalised alternatives based on viewed items; add a comparison view.",
        "channel": "Email / homepage personalisation", "owner": "Personalisation / Marketing", "urgency": "LOW",
        "message": "Still looking? We picked these based on what you viewed.",
    },
    "CHECKOUT_COMPLEXITY": {
        "label": "Checkout complexity",
        "action": "Enable guest checkout / autofill / fewer form fields; send a resume-checkout link.",
        "channel": "Email + push", "owner": "Product / UX", "urgency": "MEDIUM",
        "message": "Finish your order in 30 seconds - your details are saved.",
    },
    "POST_PURCHASE_ISSUE": {
        "label": "Post-purchase / service issue",
        "action": "Proactively contact the customer with order status, apology and compensation credit; escalate to support.",
        "channel": "Phone / WhatsApp", "owner": "Customer Support", "urgency": "HIGH",
        "message": "We're sorry your order is delayed. Here's a live update and a Rs.100 credit.",
    },
    "NONE": {
        "label": "No significant friction",
        "action": "No action needed.", "channel": "-", "owner": "-", "urgency": "NONE", "message": "",
    },
}

# Feedback keyword lists per cause (v1 lists kept, a few forms added). Matching is now whole-word.
KEYWORDS = {
    "PAYMENT_FAILURE": ["payment", "declined", "failed", "otp", "transaction", "card", "upi",
                        "money deducted", "deducted"],
    "DELIVERY_UNCERTAINTY": ["delivery", "shipping", "arrive", "pincode", "late", "when will"],
    "UNCLEAR_PRODUCT_INFO": ["size", "specs", "description", "unclear", "not sure", "material",
                             "photos", "compatible"],
    "PRICE_SHOCK": ["expensive", "charges", "extra", "hidden", "coupon", "price", "tax"],
    "POOR_RECOMMENDATIONS": ["recommend", "irrelevant", "can't find", "options", "similar"],
    "CHECKOUT_COMPLEXITY": ["form", "address", "signup", "login", "too many steps", "complicated"],
    "POST_PURCHASE_ISSUE": ["refund", "delayed order", "not received", "damaged", "support", "return"],
}

# Short theme names used in the structured feedback result
THEME_NAMES = {
    "PAYMENT_FAILURE": "payment", "DELIVERY_UNCERTAINTY": "delivery", "UNCLEAR_PRODUCT_INFO": "product_info",
    "PRICE_SHOCK": "price", "POOR_RECOMMENDATIONS": "recommendations", "CHECKOUT_COMPLEXITY": "checkout",
    "POST_PURCHASE_ISSUE": "post_purchase",
}

NEGATIVE_WORDS = ["failed", "failing", "declined", "error", "problem", "issue", "not sure", "unclear",
                  "confusing", "expensive", "hidden", "extra charges", "late", "delayed", "delay", "worst",
                  "terrible", "bad", "angry", "frustrated", "refund", "damaged", "not received",
                  "complicated", "cheat", "fraud", "scam", "deducted", "money deducted", "poor", "slow",
                  "irrelevant", "can't find", "unable", "disappointed", "waste", "never again", "not working"]
POSITIVE_WORDS = ["great", "good", "love", "fast", "easy", "smooth", "happy", "excellent", "thanks",
                  "thank you", "helpful", "satisfied", "perfect", "quick", "awesome"]
STRONG_NEGATIVE = ["money deducted", "deducted", "refund", "fraud", "cheat", "scam", "worst", "terrible",
                   "angry", "never again", "double charged", "charged twice"]

KNOWN_EVENT_TYPES = {
    "page_view", "search", "product_view", "compare", "review_read", "size_chart_view", "add_to_cart",
    "remove_from_cart", "view_cart", "delivery_check", "shipping_cost_shown", "coupon_failed",
    "checkout_start", "form_error", "payment_attempt", "payment_failed", "purchase", "support_chat",
    "support_ticket", "order_delayed", "session_exit",
}

# Which journey stage does an event belong to? (delivery_check / coupon_failed depend on context)
STAGE_OF_EVENT = {
    "page_view": "BROWSING", "search": "BROWSING",
    "product_view": "PRODUCT_EVALUATION", "compare": "PRODUCT_EVALUATION",
    "review_read": "PRODUCT_EVALUATION", "size_chart_view": "PRODUCT_EVALUATION",
    "add_to_cart": "CART", "remove_from_cart": "CART", "view_cart": "CART",
    "checkout_start": "CHECKOUT", "form_error": "CHECKOUT", "shipping_cost_shown": "CHECKOUT",
    "payment_attempt": "PAYMENT", "payment_failed": "PAYMENT",
    "purchase": "POST_PURCHASE", "order_delayed": "POST_PURCHASE",
    "support_chat": "SUPPORT", "support_ticket": "SUPPORT",
}

# If the LAST friction event before exit is this event, it points to this cause
EVENT_TO_CAUSE = {
    "payment_failed": "PAYMENT_FAILURE", "coupon_failed": "PRICE_SHOCK", "shipping_cost_shown": "PRICE_SHOCK",
    "remove_from_cart": "PRICE_SHOCK", "form_error": "CHECKOUT_COMPLEXITY",
    "delivery_check": "DELIVERY_UNCERTAINTY", "order_delayed": "POST_PURCHASE_ISSUE",
}

MIN_CAUSE_SCORE = 0.25      # below this a cause is ignored
TIE_MARGIN = 0.10           # causes this close to the top are "tied" -> use the last friction event
NEAR_EXIT_SECONDS = 60      # "left right after friction" window
SLOW_DELIVERY_DAYS = 5      # delivery estimate at/above this counts as slow
ABANDONED_STATUSES = ("CART_ABANDONED", "BROWSE_DROPOFF")
# Order used only to break exact ties between causes
CAUSE_PRIORITY = ["PAYMENT_FAILURE", "POST_PURCHASE_ISSUE", "DELIVERY_UNCERTAINTY", "PRICE_SHOCK",
                  "CHECKOUT_COMPLEXITY", "UNCLEAR_PRODUCT_INFO", "POOR_RECOMMENDATIONS"]

CONFIDENCE_NOTE = ("Rule-based heuristic score built from hand-written rules. It is NOT a statistically "
                   "validated probability; no real customer data was used to calibrate it.")
RISK_NOTE = ("Rule-based heuristic score from 0 to 100. It is NOT a probability of churn; "
             "no real customer data was used to calibrate it.")


# =====================================================================
# 2. PREPROCESSING  (raw data -> validated clean dataset + quality report)
# =====================================================================
def new_quality_report() -> Dict[str, int]:
    """Counters that describe how messy the raw data was. Nothing is hidden."""
    return {
        "sessions": 0, "total_events": 0, "duplicates_removed": 0, "invalid_events": 0,
        "unknown_event_types": 0, "missing_timestamps": 0, "invalid_timestamps": 0,
        "imputed_timestamps": 0, "events_without_metadata": 0, "missing_customer_ids": 0,
        "missing_session_ids": 0, "missing_feedback": 0, "clean_events": 0,
    }


def parse_timestamp(value: Any) -> Optional[float]:
    """Convert a number / numeric string / ISO string to seconds. Returns None if impossible."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:                      # no timezone given -> assume UTC
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
    else:
        return None
    if not math.isfinite(number):
        return None
    return number / 1000.0 if number > 1e11 else number    # milliseconds -> seconds


def clean_feedback_text(text: Any) -> str:
    """Lowercase, fix quotes, drop odd symbols, squash repeated punctuation and spaces.
    Meaningful words (and apostrophes such as can't) are preserved."""
    if text is None:
        return ""
    cleaned = str(text).lower()
    cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    cleaned = re.sub(r"[^\w\s'.,!?%-]", " ", cleaned)      # remove emojis / symbols
    cleaned = re.sub(r"([.,!?-])\1+", r"\1", cleaned)      # "!!!" -> "!"
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_event_type(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


def _clean_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_session(raw: Any, quality: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Clean ONE raw session. Raises ValueError if the session is not usable at all.

    Duplicate rule: two events are duplicates only if session, customer, type, timestamp AND
    metadata are all identical. Two payment attempts at different times are kept.
    Events with a missing timestamp are never treated as duplicates (we cannot be sure)."""
    if not isinstance(raw, dict):
        raise ValueError("Each session must be a JSON object (dict), got " + type(raw).__name__)
    raw_events = raw.get("events")
    if raw_events is None:
        raw_events = []
    if not isinstance(raw_events, list):
        raise ValueError("'events' must be a list")

    q = new_quality_report()
    q["sessions"] = 1
    issues: List[str] = []

    session_id = _clean_id(raw.get("session_id"))
    if session_id is None:
        session_id = "UNKNOWN_SESSION"; q["missing_session_ids"] += 1
        issues.append("session_id missing -> 'UNKNOWN_SESSION'")
    customer_id = _clean_id(raw.get("customer_id"))
    if customer_id is None:
        customer_id = "UNKNOWN_CUSTOMER"; q["missing_customer_ids"] += 1
        issues.append("customer_id missing -> 'UNKNOWN_CUSTOMER'")

    kept: List[Dict[str, Any]] = []
    seen = set()
    for item in raw_events:
        q["total_events"] += 1
        if not isinstance(item, dict):
            q["invalid_events"] += 1; continue
        event_type = _normalize_event_type(item.get("type"))
        if not event_type:
            q["invalid_events"] += 1; continue           # no usable event type -> cannot use it
        if event_type not in KNOWN_EVENT_TYPES:
            q["unknown_event_types"] += 1                # kept, but no detector uses it
        meta = item.get("meta")
        if not isinstance(meta, dict):
            meta = {}; q["events_without_metadata"] += 1
        raw_ts = item.get("ts")
        parsed = parse_timestamp(raw_ts)
        if raw_ts is None or (isinstance(raw_ts, str) and not raw_ts.strip()):
            q["missing_timestamps"] += 1
        elif parsed is None:
            q["invalid_timestamps"] += 1
        if parsed is not None:                           # duplicate check (needs a real timestamp)
            key = (session_id, customer_id, event_type, parsed, json.dumps(meta, sort_keys=True, default=str))
            if key in seen:
                q["duplicates_removed"] += 1; continue
            seen.add(key)
        kept.append({"type": event_type, "ts_abs": parsed, "ts_raw": raw_ts, "meta": dict(meta),
                     "ts_imputed": parsed is None})

    # --- fill missing timestamps: copy the previous known one (or the first known one) ---
    first_known = next((e["ts_abs"] for e in kept if e["ts_abs"] is not None), None)
    last_known = None
    for e in kept:
        if e["ts_abs"] is not None:
            last_known = e["ts_abs"]; e["ts_filled"] = last_known
        elif last_known is not None:
            e["ts_filled"] = last_known
        else:
            e["ts_filled"] = first_known if first_known is not None else 0.0
    # --- normalise: "ts" = seconds since the first event of the session ---
    base = min((e["ts_filled"] for e in kept), default=0.0)
    for e in kept:
        e["ts"] = round(e["ts_filled"] - base, 3)
        del e["ts_abs"], e["ts_filled"]
    kept.sort(key=lambda e: e["ts"])                     # stable sort keeps original order on ties

    q["clean_events"] = len(kept)
    q["imputed_timestamps"] = sum(1 for e in kept if e["ts_imputed"])
    if q["imputed_timestamps"]:
        issues.append(f"{q['imputed_timestamps']} event(s) had no usable timestamp; estimated from neighbours")
    if q["duplicates_removed"]:
        issues.append(f"{q['duplicates_removed']} duplicate event(s) removed")
    if q["invalid_events"]:
        issues.append(f"{q['invalid_events']} invalid event(s) dropped (no event type)")

    raw_feedback = "" if raw.get("feedback") is None else str(raw.get("feedback"))
    cleaned_feedback = clean_feedback_text(raw_feedback)
    if not cleaned_feedback:
        q["missing_feedback"] += 1

    if quality is not None:                              # add this session to the dataset-level report
        for key, value in q.items():
            quality[key] = quality.get(key, 0) + value

    return {"session_id": session_id, "customer_id": customer_id, "events": kept,
            "raw_feedback": raw_feedback, "cleaned_feedback": cleaned_feedback,
            "data_quality": q, "data_issues": issues}


def preprocess_dataset(raw_sessions: List[Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """Clean a whole dataset. Returns (clean_sessions, data_quality_report, errors).
    Unusable sessions are skipped but REPORTED in errors (never silently dropped)."""
    quality = new_quality_report()
    clean, errors = [], []
    seen_ids = Counter()
    for index, raw in enumerate(raw_sessions):
        try:
            session = clean_session(raw, quality)
        except ValueError as err:
            errors.append({"index": index, "error": str(err)}); continue
        clean.append(session)
        if session["session_id"] != "UNKNOWN_SESSION":
            seen_ids[session["session_id"]] += 1
    quality["duplicate_session_ids"] = sum(1 for n in seen_ids.values() if n > 1)
    quality["unusable_sessions"] = len(errors)
    return clean, quality, errors


# =====================================================================
# 3. FEEDBACK ANALYSIS  (rule-based fallback + optional LLM)
# =====================================================================
def _find_words(text: str, words: List[str]) -> List[str]:
    """Whole-word / whole-phrase matches, so 'late' does not match 'chocolate'."""
    return [w for w in words if re.search(r"\b" + re.escape(w) + r"\b", text)]


def classify_feedback(text: str) -> Dict[str, List[str]]:
    """v1 function (kept): cause -> matched keywords. Now matches whole words only."""
    text = (text or "").lower()
    found = {}
    for cause, words in KEYWORDS.items():
        hits = _find_words(text, words)
        if hits:
            found[cause] = hits
    return found


def analyze_feedback_rules(cleaned: str) -> Dict[str, Any]:
    """Rule-based feedback analysis. Always available, needs no API key."""
    empty = {"sentiment": "none", "themes": [], "cause_hints": {}, "severity": "none",
             "keywords": [], "method": "rules"}
    if not cleaned:
        return empty
    negative = _find_words(cleaned, NEGATIVE_WORDS)
    positive = _find_words(cleaned, POSITIVE_WORDS)
    strong = _find_words(cleaned, STRONG_NEGATIVE)
    hints = classify_feedback(cleaned)
    if len(negative) > len(positive):
        sentiment = "negative"
    elif len(positive) > len(negative):
        sentiment = "positive"
    else:
        sentiment = "neutral"
    severity = "none"
    if sentiment == "negative":
        severity = "high" if (strong or len(negative) >= 3) else "medium" if len(negative) == 2 else "low"
    keywords: List[str] = []
    for word in negative + [k for hits in hints.values() for k in hits]:
        if word not in keywords:
            keywords.append(word)
    return {"sentiment": sentiment, "themes": [THEME_NAMES[c] for c in hints], "cause_hints": hints,
            "severity": severity, "keywords": keywords, "method": "rules"}


def analyze_feedback_llm(raw_text: str) -> Optional[Dict[str, Any]]:
    """OPTIONAL semantic analysis with an LLM. Returns None on ANY problem (no key, no package,
    network error, bad JSON) so the caller falls back to rules."""
    if not raw_text.strip() or not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        prompt = ("Classify this e-commerce customer feedback. Reply with ONLY JSON: "
                  '{"sentiment": "negative|neutral|positive", "themes": [..], "severity": "none|low|medium|high", '
                  '"keywords": [..]}. Allowed themes: ' + ", ".join(THEME_NAMES.values()) +
                  f"\nFeedback: {raw_text[:1000]}")
        msg = client.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                                     max_tokens=200, messages=[{"role": "user", "content": prompt}])
        data = json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group(0))
        theme_to_cause = {v: k for k, v in THEME_NAMES.items()}
        themes = [t for t in data.get("themes", []) if t in theme_to_cause]
        sentiment = data.get("sentiment") if data.get("sentiment") in ("negative", "neutral", "positive") else "neutral"
        severity = data.get("severity") if data.get("severity") in ("none", "low", "medium", "high") else "low"
        keywords = [str(k) for k in data.get("keywords", [])][:8]
        return {"sentiment": sentiment, "themes": themes, "severity": severity, "keywords": keywords,
                "cause_hints": {theme_to_cause[t]: keywords for t in themes}, "method": "llm"}
    except Exception:
        return None


def analyze_feedback(cleaned: str, use_llm: bool = False, raw_text: str = "") -> Dict[str, Any]:
    """Structured feedback result. LLM only if asked AND available; otherwise rules."""
    if use_llm:
        llm_result = analyze_feedback_llm(raw_text or cleaned)
        if llm_result is not None:
            return llm_result
    return analyze_feedback_rules(cleaned)


# =====================================================================
# 4. FEATURE ENGINEERING  (numeric, ML-ready)
# =====================================================================
def safe_divide(a: float, b: float) -> float:
    return 0.0 if not b else a / b


def first_ts(events: List[dict], event_type: str) -> Optional[float]:
    for e in events:
        if e["type"] == event_type:
            return e["ts"]
    return None


def _gap(start: Optional[float], end: Optional[float]) -> Optional[float]:
    """Seconds between two moments, or None if either is missing / order is wrong."""
    if start is None or end is None or end < start:
        return None
    return round(end - start, 2)


def real_events(events: List[dict]) -> List[dict]:
    return [e for e in events if e["type"] != "session_exit"]


def get_exit_ts(events: List[dict]) -> float:
    """Exit time = a 'session_exit' event if present, otherwise the last event."""
    exit_ts = first_ts(events, "session_exit")
    if exit_ts is not None:
        return exit_ts
    return events[-1]["ts"] if events else 0.0


def describe_friction(event: dict) -> Optional[str]:
    """Human text if this event is a friction signal, else None."""
    t, meta = event["type"], event["meta"]
    if t == "payment_failed": return "Payment failed"
    if t == "coupon_failed": return "Coupon failed"
    if t == "form_error": return "Form / validation error"
    if t == "order_delayed": return "Order delayed"
    if t == "remove_from_cart": return "Item removed from cart"
    if t in ("support_chat", "support_ticket"): return "Customer contacted support"
    if t == "shipping_cost_shown" and (meta.get("shipping_cost") or 0) > 0:
        return f"Shipping cost Rs.{meta.get('shipping_cost')} shown"
    if t == "delivery_check":
        days = meta.get("delivery_days")
        return f"Delivery checked (estimate {days} days)" if days else "Delivery checked"
    return None


def find_last_friction(events: List[dict]) -> Tuple[Optional[dict], int]:
    """Last friction event and how many real events came after it."""
    real = real_events(events)
    for index in range(len(real) - 1, -1, -1):
        if describe_friction(real[index]) is not None:
            return real[index], len(real) - 1 - index
    return None, 0


def _meta_numbers(events: List[dict], event_type: str, key: str) -> List[float]:
    return [e["meta"][key] for e in events
            if e["type"] == event_type and isinstance(e["meta"].get(key), (int, float))
            and not isinstance(e["meta"].get(key), bool)]


def engineer_features(clean: Dict[str, Any], feedback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Turn a clean session into flat numeric features (0/1 for yes/no, None = not computable).
    These same features can later feed a machine-learning model."""
    events = clean["events"]
    if feedback is None:
        feedback = analyze_feedback_rules(clean.get("cleaned_feedback", ""))
    n = Counter(e["type"] for e in events)

    attempts, failures = n["payment_attempt"], n["payment_failed"]
    carts, removals = n["add_to_cart"], n["remove_from_cart"]
    purchase_ts = first_ts(events, "purchase")
    checkout_ts = first_ts(events, "checkout_start")
    exit_ts = get_exit_ts(events)
    start_ts = events[0]["ts"] if events else 0.0

    # checkout duration: checkout start -> purchase (or exit if no purchase)
    checkout_duration = 0.0
    if checkout_ts is not None:
        end = purchase_ts if (purchase_ts is not None and purchase_ts >= checkout_ts) else exit_ts
        checkout_duration = max(0.0, end - checkout_ts)

    # time gaps (seconds) between journey steps
    gaps_attempt_to_fail, pending_attempt = [], None
    for e in events:
        if e["type"] == "payment_attempt":
            pending_attempt = e["ts"]
        elif e["type"] == "payment_failed" and pending_attempt is not None:
            gaps_attempt_to_fail.append(e["ts"] - pending_attempt); pending_attempt = None
    last_friction, _ = find_last_friction(events)

    delivery_days_list = _meta_numbers(events, "delivery_check", "delivery_days")
    ship_costs = _meta_numbers(events, "shipping_cost_shown", "shipping_cost")
    categories = {e["meta"].get("category") for e in events if e["meta"].get("category")}
    cart_prices = _meta_numbers(events, "add_to_cart", "price")
    support_events = [e for e in events if e["type"] in ("support_chat", "support_ticket")]
    post_purchase_support = (sum(1 for e in support_events if e["ts"] >= purchase_ts)
                             if purchase_ts is not None else 0)
    text = clean.get("cleaned_feedback", "")

    return {
        # payment
        "payment_attempts": attempts,
        "payment_failures": failures,
        "payment_failure_rate": round(min(1.0, safe_divide(failures, max(attempts, failures))), 3),
        # time
        "session_duration": round(exit_ts - start_ts, 2),
        "checkout_duration": round(checkout_duration, 2),
        "time_view_to_cart": _gap(first_ts(events, "product_view"), first_ts(events, "add_to_cart")),
        "time_cart_to_checkout": _gap(first_ts(events, "add_to_cart"), checkout_ts),
        "time_checkout_to_payment": _gap(checkout_ts, first_ts(events, "payment_attempt")),
        "time_attempt_to_failure": (round(sum(gaps_attempt_to_fail) / len(gaps_attempt_to_fail), 2)
                                    if gaps_attempt_to_fail else None),
        "time_friction_to_exit": _gap(last_friction["ts"], exit_ts) if last_friction else None,
        # browsing / evaluation
        "product_views": n["product_view"],
        "search_count": n["search"],
        "comparison_count": n["compare"],
        "review_reads": n["review_read"],
        "size_chart_views": n["size_chart_view"],
        "categories_browsed": len(categories),
        # cart
        "cart_additions": carts,
        "cart_removals": removals,
        "cart_removal_rate": round(min(1.0, safe_divide(removals, carts)), 3),
        "cart_value": round(sum(cart_prices), 2),
        # delivery / price
        "delivery_checks": n["delivery_check"],
        "delivery_days": delivery_days_list[-1] if delivery_days_list else 0,   # 0 = not shown
        "shipping_cost": max(ship_costs) if ship_costs else 0,
        "coupon_failures": n["coupon_failed"],
        # checkout
        "checkout_started": 1 if checkout_ts is not None else 0,
        "form_errors": n["form_error"],
        # support / post purchase
        "support_tickets": n["support_ticket"],
        "support_chats": n["support_chat"],
        "post_purchase_support_contacts": post_purchase_support,
        "order_delays": n["order_delayed"],
        # feedback
        "negative_feedback": 1 if feedback["sentiment"] == "negative" else 0,
        "positive_feedback": 1 if feedback["sentiment"] == "positive" else 0,
        "money_deducted_reported": 1 if _find_words(text, ["deducted", "money deducted", "charged twice", "double charged"]) else 0,
        # outcome
        "purchase_completed": 1 if n["purchase"] else 0,
        "cart_abandoned": 1 if (carts and not n["purchase"]) else 0,
    }


def extract_features(session: dict) -> Dict[str, Any]:
    """v1 name kept for compatibility: raw session -> engineered features."""
    return engineer_features(clean_session(session))


# =====================================================================
# 5. CUSTOMER JOURNEY ANALYSIS  (order of events, not just counts)
# =====================================================================
def stage_of(event_type: str, reached: set) -> Optional[str]:
    """Journey stage of an event. Some events depend on what already happened."""
    if event_type == "delivery_check":
        return "CART" if "CART" in reached else "PRODUCT_EVALUATION"
    if event_type == "coupon_failed":
        return "CHECKOUT" if "CHECKOUT" in reached else "CART"
    return STAGE_OF_EVENT.get(event_type)


def analyze_journey(clean: Dict[str, Any]) -> Dict[str, Any]:
    """Build a stage timeline and describe what happened just before the customer left."""
    events = clean["events"]
    segments: List[Dict[str, Any]] = []
    reached: set = set()
    for e in real_events(events):
        stage = stage_of(e["type"], reached)
        if stage is None:
            continue                                     # e.g. unknown event types
        reached.add(stage)
        if not segments or segments[-1]["stage"] != stage:
            segments.append({"stage": stage, "start_ts": e["ts"], "end_ts": e["ts"],
                             "events": [], "friction_points": []})
        segment = segments[-1]
        segment["end_ts"] = e["ts"]
        segment["events"].append({"type": e["type"], "ts": e["ts"]})
        description = describe_friction(e)
        if description:
            segment["friction_points"].append({"event_type": e["type"], "ts": e["ts"], "description": description})

    purchased = any(e["type"] == "purchase" for e in events)
    last_friction, events_after = find_last_friction(events)
    exit_ts = get_exit_ts(events)
    seconds_to_exit = _gap(last_friction["ts"], exit_ts) if last_friction else None

    # "meaningful" stage = last stage, ignoring SUPPORT (a support chat is not where the journey ended)
    last_stage = segments[-1]["stage"] if segments else "NO_ACTIVITY"
    meaningful = next((s["stage"] for s in reversed(segments) if s["stage"] != "SUPPORT"), last_stage)

    ended_after_friction = bool(
        last_friction and not purchased
        and (events_after == 0 or (seconds_to_exit is not None and seconds_to_exit <= NEAR_EXIT_SECONDS)))
    return {
        "stages_reached": list(dict.fromkeys(s["stage"] for s in segments)),   # unique, in order
        "timeline": segments,
        "sequence": [e["type"] for e in real_events(events)],
        "last_stage": last_stage,
        "last_meaningful_stage": meaningful,
        "purchased": purchased,
        "last_friction_event": ({"type": last_friction["type"], "ts": last_friction["ts"],
                                 "description": describe_friction(last_friction)} if last_friction else None),
        "events_after_last_friction": events_after,
        "seconds_from_last_friction_to_exit": seconds_to_exit,
        "ended_after_friction": ended_after_friction,
        "cause_of_last_friction": EVENT_TO_CAUSE.get(last_friction["type"]) if last_friction else None,
        "exit_ts": exit_ts,
    }


# =====================================================================
# 6. FRICTION DETECTORS  (rule-based; each returns (score 0-1, structured evidence))
# =====================================================================
def make_evidence(text: str, importance: str = "MEDIUM", event_type: Optional[str] = None,
                  events: Optional[List[dict]] = None, count: Optional[int] = None) -> Dict[str, Any]:
    """One piece of evidence. If event_type + events are given, count and timestamps come from the data."""
    item: Dict[str, Any] = {"text": text, "event_type": event_type, "count": count,
                            "timestamps": [], "importance": importance}
    if event_type and events is not None:
        times = [e["ts"] for e in events if e["type"] == event_type]
        item["count"], item["timestamps"] = len(times), times
    return item


class Signals:
    """Small helper: a detector adds signals (points + evidence); result() gives (score, evidence)."""
    def __init__(self, events: List[dict]):
        self.events, self.score, self.evidence = events, 0.0, []

    def add(self, points: float, text: str, importance: str = "MEDIUM", event_type: Optional[str] = None) -> None:
        self.score += points
        self.evidence.append(make_evidence(text, importance, event_type, self.events))

    def result(self) -> Tuple[float, List[dict]]:
        return min(self.score, 1.0), self.evidence


def _payment(clean, f, j, fb):
    s = Signals(clean["events"])
    if f["payment_attempts"]:
        s.evidence.append(make_evidence(f"{f['payment_attempts']} payment attempt(s)", "LOW", "payment_attempt", clean["events"]))
    if f["payment_failures"]:
        s.add(0.40, f"{f['payment_failures']} payment failure(s)", "HIGH", "payment_failed")
    if f["payment_failures"] >= 2:
        s.add(0.15, "Repeated payment failures", "HIGH")
    if f["payment_failures"] and f["payment_failure_rate"] >= 0.5:
        s.add(0.10, f"{f['payment_failure_rate'] * 100:.1f}% payment failure rate", "MEDIUM")
    if j["ended_after_friction"] and j["cause_of_last_friction"] == "PAYMENT_FAILURE":
        secs = j["seconds_from_last_friction_to_exit"]
        s.add(0.20, f"Customer exited after payment failure ({secs:g}s before exit)", "HIGH")
    if f["time_attempt_to_failure"] is not None and f["time_attempt_to_failure"] <= 10:
        s.add(0.05, f"Failures returned almost instantly (avg {f['time_attempt_to_failure']:g}s) - suggests bank/gateway decline", "LOW")
    if f["money_deducted_reported"]:
        s.add(0.15, "Customer reports money was deducted", "HIGH")
    return s.result()


def _delivery(clean, f, j, fb):
    s = Signals(clean["events"])
    if f["delivery_checks"] >= 1:
        s.add(0.25, f"Delivery checked {f['delivery_checks']} time(s)", "MEDIUM", "delivery_check")
    if f["delivery_checks"] >= 2:
        s.add(0.15, "Repeated delivery checks show uncertainty", "MEDIUM")
    if f["delivery_days"] >= SLOW_DELIVERY_DAYS:
        s.add(0.15, f"Estimated delivery: {f['delivery_days']:g} days (slow)", "HIGH")
    if j["ended_after_friction"] and j["cause_of_last_friction"] == "DELIVERY_UNCERTAINTY":
        s.add(0.20, "Session ended after delivery check", "HIGH")
    if f["delivery_checks"] and not f["purchase_completed"]:
        s.add(0.10, "Customer did not purchase after checking delivery", "MEDIUM")
    if f["order_delays"]:
        s.add(0.20, f"Order delay recorded ({f['order_delays']}x)", "HIGH", "order_delayed")
    if f["delivery_checks"] and f["shipping_cost"] > 0 and not f["purchase_completed"]:
        s.add(0.05, f"Delivery charge Rs.{f['shipping_cost']:g} shown", "LOW", "shipping_cost_shown")
    return s.result()


def _product_info(clean, f, j, fb):
    s = Signals(clean["events"])
    no_cart = not f["cart_additions"]
    if f["product_views"] >= 4 and no_cart:
        s.add(0.20, f"{f['product_views']} product views, product was not added to cart", "MEDIUM", "product_view")
    if f["size_chart_views"] >= 1:
        s.add(0.20, "Size guide / spec details opened", "MEDIUM", "size_chart_view")
    if f["review_reads"] >= 2:
        s.add(0.20, f"{f['review_reads']} reviews read looking for reassurance", "MEDIUM", "review_read")
    support = f["support_chats"] + f["support_tickets"]
    if support and no_cart:
        s.add(0.20, "Asked support before adding to cart", "HIGH")
    return s.result()


def _price(clean, f, j, fb):
    s = Signals(clean["events"])
    if f["coupon_failures"]:
        s.add(0.30 + 0.10 * min(f["coupon_failures"] - 1, 2), f"{f['coupon_failures']} coupon failure(s)", "HIGH", "coupon_failed")
    if f["shipping_cost"] > 0:
        s.add(0.30, f"Shipping cost Rs.{f['shipping_cost']:g} revealed at checkout", "HIGH", "shipping_cost_shown")
        if f["cart_value"] > 0 and f["shipping_cost"] / f["cart_value"] >= 0.15:
            s.add(0.10, f"Shipping is {f['shipping_cost'] / f['cart_value'] * 100:.0f}% of cart value", "MEDIUM")
    if f["cart_removals"] and f["cart_additions"]:
        s.add(0.20, f"Removed items from cart ({f['cart_removal_rate'] * 100:.0f}% of additions)", "MEDIUM", "remove_from_cart")
    if j["ended_after_friction"] and j["cause_of_last_friction"] == "PRICE_SHOCK":
        s.add(0.15, "Exited right after a price/total step", "HIGH")
    return s.result()


def _reco(clean, f, j, fb):
    s = Signals(clean["events"])
    if f["search_count"] >= 3:
        s.add(0.30, f"{f['search_count']} searches - struggling to find the right product", "MEDIUM", "search")
    if f["categories_browsed"] >= 3:
        s.add(0.25, f"Browsed {f['categories_browsed']} categories without settling", "MEDIUM")
    if f["comparison_count"] >= 2:
        s.add(0.20, f"{f['comparison_count']} product comparisons", "MEDIUM", "compare")
    if not f["cart_additions"] and f["product_views"] >= 5:
        s.add(0.15, f"{f['product_views']} product views, nothing added to cart", "LOW", "product_view")
    return s.result()


def _checkout(clean, f, j, fb):
    s = Signals(clean["events"])
    if f["form_errors"]:
        s.add(0.30 + 0.10 * min(f["form_errors"] - 1, 3), f"{f['form_errors']} form/validation error(s)", "HIGH", "form_error")
    if f["checkout_started"] and not f["payment_attempts"] and not f["purchase_completed"]:
        s.add(0.30, "Started checkout but never attempted payment", "HIGH", "checkout_start")
    if f["checkout_duration"] > 600 and f["checkout_started"]:
        s.add(0.10, f"Very long checkout ({f['checkout_duration']:g}s)", "MEDIUM")
    if (f["checkout_started"] and not f["purchase_completed"] and j["last_meaningful_stage"] == "CHECKOUT"):
        s.add(0.10, "Session ended during the checkout stage", "MEDIUM")
    return s.result()


def _post(clean, f, j, fb):
    s = Signals(clean["events"])
    if f["order_delays"]:
        s.add(0.45, "Order delay recorded", "HIGH", "order_delayed")
    if f["purchase_completed"] and f["post_purchase_support_contacts"]:
        s.add(0.30, "Contacted support after purchase", "HIGH")
    if f["support_chats"] + f["support_tickets"] >= 2:
        s.add(0.15, "Repeated support contact", "HIGH")
    if f["support_tickets"]:
        s.add(0.15, f"{f['support_tickets']} support ticket(s) opened", "HIGH", "support_ticket")
    return s.result()


DETECTORS = {
    "PAYMENT_FAILURE": _payment, "DELIVERY_UNCERTAINTY": _delivery, "UNCLEAR_PRODUCT_INFO": _product_info,
    "PRICE_SHOCK": _price, "POOR_RECOMMENDATIONS": _reco, "CHECKOUT_COMPLEXITY": _checkout,
    "POST_PURCHASE_ISSUE": _post,
}


def detect_causes(clean, f, j, fb) -> Tuple[Dict[str, float], Dict[str, List[dict]]]:
    """Run every detector. Negative feedback that mentions the same theme adds to the score.
    Returns (cause_scores, evidence_per_cause); causes with score 0 are left out."""
    scores: Dict[str, float] = {}
    evidence: Dict[str, List[dict]] = {}
    for cause, detector in DETECTORS.items():
        score, ev = detector(clean, f, j, fb)
        if fb["sentiment"] == "negative" and cause in fb["cause_hints"]:      # feedback corroborates
            score += 0.25 + (0.05 if fb["severity"] == "high" else 0)
            words = ", ".join(fb["cause_hints"][cause][:3]) or THEME_NAMES[cause]
            ev.append(make_evidence(f"Negative customer feedback mentions: {words}", "HIGH", "feedback", count=1))
        if score > 0:
            scores[cause] = round(min(score, 1.0), 2)
            evidence[cause] = ev
    return dict(sorted(scores.items(), key=lambda kv: -kv[1])), evidence


# =====================================================================
# 7. STATUS, CAUSE SELECTION, CONFIDENCE, RISK
# =====================================================================
def determine_status(clean, f, cause_scores) -> str:
    if not clean["events"]:
        return "NO_ACTIVITY"
    if f["purchase_completed"]:
        if cause_scores.get("POST_PURCHASE_ISSUE", 0) >= MIN_CAUSE_SCORE:
            return "PURCHASED_WITH_ISSUE"
        if any(s >= MIN_CAUSE_SCORE for s in cause_scores.values()):
            return "CONVERTED_AFTER_FRICTION"        # had friction but still bought
        return "CONVERTED"
    return "CART_ABANDONED" if f["cart_additions"] else "BROWSE_DROPOFF"


def select_causes(scores: Dict[str, float], j: Dict[str, Any], purchased: bool) -> Tuple[Optional[str], List[str], str]:
    """Pick primary + secondary causes. Not just 'highest score':
    (1) a purchased customer with an open post-purchase problem -> that problem is primary;
    (2) causes within TIE_MARGIN of the top are tied -> prefer the one matching the LAST friction event."""
    ranked = sorted(((c, s) for c, s in scores.items() if s >= MIN_CAUSE_SCORE),
                    key=lambda cs: (-cs[1], CAUSE_PRIORITY.index(cs[0])))
    if not ranked:
        return None, [], "No cause reached the minimum score of %.2f." % MIN_CAUSE_SCORE
    primary, top_score = ranked[0]
    reason = f"{primary} has the highest score ({top_score:.2f})"
    if len(ranked) > 1:
        reason += f", {top_score - ranked[1][1]:.2f} ahead of {ranked[1][0]} ({ranked[1][1]:.2f})"
    else:
        reason += " and no other cause reached the minimum score"

    if purchased and primary != "POST_PURCHASE_ISSUE" and scores.get("POST_PURCHASE_ISSUE", 0) >= MIN_CAUSE_SCORE:
        primary = "POST_PURCHASE_ISSUE"
        reason = ("Customer already purchased, so the open problem is post-purchase "
                  f"(POST_PURCHASE_ISSUE score {scores[primary]:.2f}).")
    else:
        tied = [c for c, s in ranked if top_score - s <= TIE_MARGIN]
        last_cause = j["cause_of_last_friction"]
        if len(tied) > 1 and last_cause in tied and last_cause != primary:
            reason = (f"{last_cause} was within {TIE_MARGIN:.2f} of the top score and matches the last "
                      "friction event before exit, so it was chosen over " + primary + ".")
            primary = last_cause
        elif primary == last_cause and j["ended_after_friction"]:
            reason += "; it also matches the last friction event before the customer left"
    secondary = [c for c, _ in ranked if c != primary][:2]
    return primary, secondary, reason if reason.endswith(".") else reason + "."


def calculate_confidence(primary: str, scores: Dict[str, float], evidence: List[dict], j, f,
                         quality: Dict[str, int]) -> Tuple[float, str, List[str]]:
    """Rule-based confidence (0.30-0.95) + the reasons behind it. NOT a calibrated probability."""
    top = scores[primary]
    others = [s for c, s in scores.items() if c != primary]
    second = max(others) if others else 0.0
    second_name = next((c for c, s in scores.items() if c != primary and s == second), None)
    margin = top - second
    value = 0.30 + 0.30 * min(top, 1.0) + 0.25 * min(margin, 1.0) + 0.10 * min(len(evidence), 4) / 4
    factors: List[str] = []
    factors.append("Strong combined signal strength (%.2f)" % top if top >= 0.7 else
                   "Moderate signal strength (%.2f)" % top if top >= 0.45 else
                   "Weak signal strength (%.2f)" % top)
    if not others or second == 0:
        factors.append("No competing cause detected")
    elif margin >= 0.30:
        factors.append("Clear margin over the next possible cause")
    elif second_name:
        factors.append(f"Close to {second_name} ({second:.2f}) - causes may overlap")
    for item in evidence:
        if item["count"] and item["count"] >= 2 and item["event_type"] not in (None, "feedback", "payment_attempt"):
            factors.append(f"Repeated '{item['event_type']}' events ({item['count']}x)")
            break
    if j["ended_after_friction"] and j["cause_of_last_friction"] == primary:
        factors.append("Friction occurred immediately before the customer left")
    if any(item["event_type"] == "feedback" for item in evidence):
        factors.append("Customer feedback confirms the problem")
    if quality.get("imputed_timestamps"):
        value -= 0.05
        factors.append("Some timestamps were missing and estimated - timing evidence is less reliable")
    value = round(min(0.95, max(0.30, value)), 2)
    level = "HIGH" if value >= 0.75 else "MEDIUM" if value >= 0.50 else "LOW"
    return value, level, factors


def calculate_risk(primary: str, top_score: float, status: str, f, j, fb) -> Tuple[int, str, List[dict]]:
    """Rule-based risk 0-100 with a point-by-point breakdown."""
    parts: List[Dict[str, Any]] = []

    def add(points: int, text: str) -> None:
        parts.append({"factor": text, "points": points})

    add(round(top_score * 55), f"{PLAYBOOK[primary]['label']} signal strength {top_score:.2f}")
    if status == "CART_ABANDONED":
        add(15, "Customer abandoned cart")
    if not f["purchase_completed"] and j["last_meaningful_stage"] in ("CHECKOUT", "PAYMENT"):
        add(5, f"Customer left during {j['last_meaningful_stage'].lower()} (high purchase intent)")
    if f["payment_failures"] or f["shipping_cost"]:
        add(5, "Payment failed or extra shipping cost was shown")
    if f["payment_failures"] >= 2:
        add(5, f"Payment failed {f['payment_failures']} times")
    if j["ended_after_friction"]:
        add(5, "Customer left right after a friction event")
    if fb["sentiment"] == "negative" and fb["severity"] == "high":
        add(5, "Customer feedback is strongly negative")
    total = sum(p["points"] for p in parts)
    if status == "CONVERTED_AFTER_FRICTION" and total > 30:
        add(30 - total, "Customer still completed the purchase (risk capped at 30)")
        total = 30
    total = int(max(0, min(100, total)))
    level = "HIGH" if total >= 70 else "MEDIUM" if total >= 40 else "LOW"
    return total, level, parts


# =====================================================================
# 8. RECOVERY RECOMMENDATION + BUSINESS ACTION
# =====================================================================
def build_recommendation(cause: str, clean, f, j, fb, status: str) -> Dict[str, Any]:
    """Contextual recovery action. Starts from PLAYBOOK, then adapts to what actually happened."""
    rec = dict(PLAYBOOK[cause])                       # copy, never edit the global PLAYBOOK
    extra: List[str] = []
    reason = "No significant friction detected."

    if cause == "PAYMENT_FAILURE":
        n_fail, n_try = f["payment_failures"], max(f["payment_attempts"], f["payment_failures"])
        if f["money_deducted_reported"]:
            rec["action"] = "Show payment verification/status and escalate to payments support to check the deduction"
            reason = "Customer reports money was deducted even though the payment failed"
            rec.update(channel="Phone / WhatsApp + in-app status page", owner="Payments / Customer Support", urgency="HIGH")
            extra = ["Confirm the transaction status with the bank/gateway", "Auto-refund if the order was not created"]
            rec["message"] = "We're checking your payment - if money was deducted it will be reversed or your order confirmed. Here is your live status."
        elif n_fail >= 2:
            rec["action"] = "Offer an alternate payment method (UPI / wallet / Cash on Delivery) with a saved-cart link"
            reason = f"{n_fail} payment failures out of {n_try} attempts indicate payment friction"
            rec["urgency"] = "HIGH"
            extra = ["Ask the payments team to check gateway / bank error rates"]
        else:
            rec["action"] = "Offer a one-tap payment retry"
            reason = "A single payment failure - the customer may succeed on retry"
            rec["urgency"] = "MEDIUM"
            rec["message"] = "Your payment didn't go through - your cart is saved! Retry in one tap."
    elif cause == "DELIVERY_UNCERTAINTY":
        faster = any(e["meta"].get("faster_option") for e in clean["events"] if e["type"] == "delivery_check")
        days = f["delivery_days"]
        if f["order_delays"]:
            rec["action"] = "Send a proactive delay update with a new delivery date and compensation"
            reason = "The order was delayed after purchase"
            rec["urgency"] = "HIGH"
        elif days >= SLOW_DELIVERY_DAYS and faster:
            rec["action"] = "Offer a faster delivery option at checkout"
            reason = f"Estimated delivery was {days:g} days and a faster option exists"
        elif days >= SLOW_DELIVERY_DAYS:
            rec["action"] = "Show a guaranteed delivery date and a late-delivery guarantee"
            reason = f"Estimated delivery of {days:g} days is slow"
        else:
            reason = f"Customer checked delivery {f['delivery_checks']} time(s) and did not purchase"
        eta = f"within {days:g} days" if days else "by the promised date"
        rec["message"] = rec["message"].replace("{eta}", eta)
        extra = ["Show delivery date on the product and cart page"]
    elif cause == "UNCLEAR_PRODUCT_INFO":
        parts = []
        if f["size_chart_views"]: parts.append("size guide")
        parts.append("key specifications")
        if f["review_reads"] >= 2: parts.append("review summary")
        if f["comparison_count"]: parts.append("product comparison")
        if f["support_chats"] + f["support_tickets"]: parts.append("FAQ")
        rec["action"] = "Send product help: " + ", ".join(parts)
        reason = (f"{f['product_views']} product views, {f['review_reads']} review reads and "
                  f"{f['size_chart_views']} size-guide views without adding to cart")
        extra = [p.capitalize() for p in parts]
    elif cause == "PRICE_SHOCK":
        if f["coupon_failures"]:
            rec["action"] = "Replace the failed coupon with a valid targeted offer (e.g. 10% off, 24 hours)"
            reason = f"{f['coupon_failures']} coupon failure(s) plus extra costs at checkout"
        else:
            rec["action"] = "Show the total price earlier and offer free shipping above a cart threshold"
            reason = f"Shipping cost Rs.{f['shipping_cost']:g} appeared late in the journey"
        extra = ["Show total cost (with shipping and tax) on the cart page"]
    elif cause == "POOR_RECOMMENDATIONS":
        reason = f"{f['search_count']} searches and {f['categories_browsed']} categories browsed without a purchase"
        extra = ["Add a side-by-side comparison view"]
    elif cause == "CHECKOUT_COMPLEXITY":
        if f["form_errors"]:
            rec["action"] = "Enable autofill and inline validation, and reduce unnecessary form fields"
            reason = f"{f['form_errors']} form error(s) during checkout"
        else:
            rec["action"] = "Send a resume-checkout link and offer guest checkout"
            reason = "Customer started checkout but never reached payment"
        extra = ["Resume checkout", "Guest checkout", "Autofill", "Reduce form fields"]
    elif cause == "POST_PURCHASE_ISSUE":
        contacts = f["support_chats"] + f["support_tickets"]
        rec["action"] = "Give priority support: proactive order status and refund/return assistance"
        reason = "Order problem after purchase" + (f" and {contacts} support contact(s)" if contacts else "")
        if contacts >= 2 or fb["severity"] == "high":
            rec["action"] += "; escalate to a human agent"
            rec["urgency"] = "HIGH"
        extra = ["Share live order status", "Offer refund / return", "Human escalation if unresolved"]

    if cause != "NONE" and status == "CONVERTED_AFTER_FRICTION":
        rec["action"] = ("No outreach needed (customer still purchased). Review the root cause: "
                         + rec["action"][0].lower() + rec["action"][1:])
        rec["urgency"] = "LOW"
        reason += ". The customer recovered on their own, so this is an insight, not an emergency"
    rec["reason"] = reason
    rec["additional_actions"] = extra
    return rec


WORKFLOW_TRIGGERS = {
    "PAYMENT_FAILURE": "send_payment_recovery_message", "DELIVERY_UNCERTAINTY": "send_delivery_reassurance",
    "UNCLEAR_PRODUCT_INFO": "offer_product_help", "PRICE_SHOCK": "send_targeted_offer",
    "POOR_RECOMMENDATIONS": "send_personalised_alternatives", "CHECKOUT_COMPLEXITY": "send_resume_checkout_link",
    "POST_PURCHASE_ISSUE": "create_priority_support_case",
}


def build_business_action(cause: str, rec: Dict[str, Any], status: str) -> Dict[str, Any]:
    """The workflow the business team could trigger. NOTHING is actually sent by this code."""
    if cause == "NONE":
        return {"workflow_trigger": "none", "target_team": "-", "channel": "-", "customer_message": "",
                "status": "NO_ACTION_NEEDED", "outcome_tracking": "-"}
    return {"workflow_trigger": WORKFLOW_TRIGGERS[cause], "target_team": rec["owner"], "channel": rec["channel"],
            "customer_message": rec["message"],
            "status": "READY_TO_TRIGGER" if status in ABANDONED_STATUSES + ("PURCHASED_WITH_ISSUE",) else "INSIGHT_ONLY",
            "outcome_tracking": "After acting, call record_outcome(session_id, outcome) or POST /outcome"}


# =====================================================================
# 9. OUTCOME FEEDBACK LOOP (in-memory; shows whether recoveries actually worked)
# =====================================================================
VALID_OUTCOMES = ("recovered", "not_recovered", "no_response")
OUTCOME_LOG: List[Dict[str, Any]] = []
_LAST_ANALYSIS: Dict[str, Dict[str, Any]] = {}


def record_outcome(session_id: str, outcome: str, action_taken: str = "", notes: str = "",
                   primary_cause: Optional[str] = None) -> Dict[str, Any]:
    """Store what happened after a recovery action. Cause is looked up from the last analysis if omitted."""
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {VALID_OUTCOMES}, got {outcome!r}")
    last = _LAST_ANALYSIS.get(session_id, {})
    entry = {"session_id": session_id, "outcome": outcome,
             "primary_cause": primary_cause or last.get("primary_cause", "UNKNOWN"),
             "action_taken": action_taken or last.get("action", ""), "notes": notes}
    OUTCOME_LOG.append(entry)
    return entry


def outcome_summary() -> Dict[str, Any]:
    """Recovery rate per cause, computed ONLY from outcomes you recorded."""
    by_cause: Dict[str, Counter] = {}
    for entry in OUTCOME_LOG:
        by_cause.setdefault(entry["primary_cause"], Counter())[entry["outcome"]] += 1
    summary = {}
    for cause, counts in by_cause.items():
        total = sum(counts.values())
        summary[cause] = {"total": total, "recovered": counts["recovered"],
                          "recovery_rate_pct": round(100 * counts["recovered"] / total, 1)}
    return {"total_outcomes": len(OUTCOME_LOG), "by_cause": summary,
            "note": "Based only on recorded outcomes. Small samples are unreliable."}


# =====================================================================
# 10. MAIN ANALYZER  (assembles the full problem-solving report)
# =====================================================================
def build_explanation(clean, status, primary, reason, confidence, level, evidence_texts, rec, j) -> str:
    who = f"Customer {clean['customer_id']}"
    label = PLAYBOOK[primary]["label"].lower()
    if status == "CONVERTED_AFTER_FRICTION":
        head = f"{who} hit {label} but still completed the purchase"
    elif status == "PURCHASED_WITH_ISSUE":
        head = f"{who} purchased but has an open {label}"
    else:
        head = f"{who} most likely dropped off during the {j['last_meaningful_stage']} stage due to {label}"
    return (f"{head} (rule-based confidence {int(confidence * 100)}%, {level}). Why this cause: {reason} "
            f"Key signals: {'; '.join(evidence_texts[:3])}. Recommended action: {rec['action']}.")


def analyze_clean_session(clean: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    """Analyze a session that has ALREADY been cleaned by clean_session()."""
    feedback = analyze_feedback(clean["cleaned_feedback"], use_llm, clean["raw_feedback"])
    features = engineer_features(clean, feedback)
    journey = analyze_journey(clean)
    scores, evidence = detect_causes(clean, features, journey, feedback)
    status = determine_status(clean, features, scores)
    primary, secondary, reason = select_causes(scores, journey, bool(features["purchase_completed"]))

    report: Dict[str, Any] = {
        "session_id": clean["session_id"], "customer_id": clean["customer_id"],
        "journey_stage": journey["last_meaningful_stage"], "status": status,
        "features": features, "journey": journey,
        "feedback_analysis": {k: v for k, v in feedback.items() if k != "cause_hints"},
        "raw_feedback": clean["raw_feedback"], "cleaned_feedback": clean["cleaned_feedback"],
        "data_quality": clean["data_quality"], "data_issues": clean["data_issues"],
        "cause_scores": scores,
    }
    if primary is None:                                   # nothing significant found
        rec = build_recommendation("NONE", clean, features, journey, feedback, status)
        note = ("No events were recorded for this session." if status == "NO_ACTIVITY"
                else "No meaningful friction signals were found in this session.")
        report.update({
            "primary_cause": "NONE", "cause_label": PLAYBOOK["NONE"]["label"], "primary_cause_reason": reason,
            "secondary_causes": [], "secondary_cause_names": [], "evidence": [], "evidence_details": [],
            "confidence": 0, "confidence_level": "NONE", "confidence_factors": [], "confidence_note": CONFIDENCE_NOTE,
            "risk_score": 0, "risk_level": "LOW", "risk_factors": ["No significant friction detected"],
            "risk_breakdown": [], "risk_note": RISK_NOTE, "recommendation": rec,
            "business_action": build_business_action("NONE", rec, status), "explanation": note})
        _LAST_ANALYSIS[clean["session_id"]] = {"primary_cause": "NONE", "action": rec["action"]}
        return report

    top_evidence = sorted(evidence[primary], key=lambda e: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[e["importance"]])
    evidence_texts = [e["text"] for e in top_evidence]
    confidence, conf_level, conf_factors = calculate_confidence(primary, scores, top_evidence, journey, features,
                                                                clean["data_quality"])
    risk, risk_level, risk_parts = calculate_risk(primary, scores[primary], status, features, journey, feedback)
    rec = build_recommendation(primary, clean, features, journey, feedback, status)
    report.update({
        "primary_cause": primary, "cause_label": PLAYBOOK[primary]["label"], "primary_cause_reason": reason,
        "secondary_causes": [{"cause": c, "label": PLAYBOOK[c]["label"], "score": scores[c]} for c in secondary],
        "secondary_cause_names": secondary,
        "evidence": evidence_texts, "evidence_details": top_evidence,
        "confidence": confidence, "confidence_level": conf_level, "confidence_factors": conf_factors,
        "confidence_note": CONFIDENCE_NOTE,
        "risk_score": risk, "risk_level": risk_level, "risk_factors": [p["factor"] for p in risk_parts],
        "risk_breakdown": risk_parts, "risk_note": RISK_NOTE,
        "recommendation": rec, "business_action": build_business_action(primary, rec, status),
        "explanation": build_explanation(clean, status, primary, reason, confidence, conf_level,
                                         evidence_texts, rec, journey),
    })
    _LAST_ANALYSIS[clean["session_id"]] = {"primary_cause": primary, "action": rec["action"]}
    return report


def analyze_session(session: dict, use_llm: bool = False) -> Dict[str, Any]:
    """Public entry point (same name as v1): raw session -> full analysis report.
    Raises ValueError if the session cannot be used at all."""
    return analyze_clean_session(clean_session(session), use_llm)


# =====================================================================
# 11. BATCH ANALYSIS + DATASET INSIGHTS
# =====================================================================
def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Dataset-level numbers, all computed from the results (nothing is invented)."""
    total = len(results)
    active = [r for r in results if r["status"] != "NO_ACTIVITY"]
    friction = [r for r in results if r["primary_cause"] != "NONE"]
    label_counts = Counter(r["cause_label"] for r in friction)
    pay_sessions = [r for r in results if r["features"]["payment_attempts"] > 0]
    checkout_sessions = [r for r in results if r["features"]["checkout_started"]]
    abandoned = sum(r["status"] in ABANDONED_STATUSES for r in results)
    return {
        # v1 keys (unchanged meaning)
        "total_sessions": total,
        "abandoned": abandoned,
        "high_risk": sum(r["risk_level"] == "HIGH" for r in results),
        "cause_distribution": dict(label_counts),
        "avg_confidence": round(sum(r["confidence"] for r in friction) / max(len(friction), 1), 2),
        # new insights
        "active_sessions": len(active),
        "abandonment_rate_pct": _pct(abandoned, len(active)),
        "avg_risk": round(sum(r["risk_score"] for r in results) / max(total, 1), 1),
        "most_common_cause": label_counts.most_common(1)[0][0] if label_counts else None,
        "cause_distribution_pct": {label: _pct(n, len(friction)) for label, n in label_counts.most_common()},
        "payment_failure_rate_pct": _pct(sum(r["features"]["payment_failures"] > 0 for r in pay_sessions), len(pay_sessions)),
        "delivery_issue_rate_pct": _pct(sum(r["cause_scores"].get("DELIVERY_UNCERTAINTY", 0) >= MIN_CAUSE_SCORE for r in results), total),
        "checkout_abandonment_rate_pct": _pct(sum(not r["features"]["purchase_completed"] for r in checkout_sessions), len(checkout_sessions)),
        "converted_after_friction": sum(r["status"] == "CONVERTED_AFTER_FRICTION" for r in results),
        "definitions": {
            "abandonment_rate_pct": "abandoned sessions / sessions that have at least one event",
            "avg_risk": "mean rule-based risk score over ALL sessions (no-friction sessions count as 0)",
            "cause_distribution_pct": "share of sessions with a detected primary cause, by cause",
            "payment_failure_rate_pct": "sessions with >=1 payment failure / sessions with >=1 payment attempt",
            "delivery_issue_rate_pct": "sessions whose delivery-cause score >= %.2f / all sessions" % MIN_CAUSE_SCORE,
            "checkout_abandonment_rate_pct": "checkout sessions without a purchase / sessions that started checkout",
        },
    }


def analyze_all(sessions: List[dict], use_llm: bool = False) -> Dict[str, Any]:
    """Batch analysis. Same 'results' + 'summary' as v1, plus data_quality and errors."""
    clean_sessions, quality, errors = preprocess_dataset(sessions)
    results = [analyze_clean_session(c, use_llm) for c in clean_sessions]
    return {"results": results, "summary": summarize_results(results), "data_quality": quality, "errors": errors}


# =====================================================================
# 12. OPTIONAL: LLM-written explanation (kept from v1; works without a key)
# =====================================================================
def llm_explain(result: Dict[str, Any], session: Optional[dict] = None) -> str:
    """Falls back to the rule-based explanation if there is no API key / package / network."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return result["explanation"]
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), max_tokens=300,
            messages=[{"role": "user", "content":
                "You are an e-commerce recovery assistant. In 3 short sentences explain to a business "
                "manager why this customer abandoned, then write a 1-line personalised recovery message.\n"
                f"Analysis: {result}\nFeedback: {(session or {}).get('feedback', '')}"}])
        return msg.content[0].text
    except Exception:
        return result["explanation"]


# =====================================================================
# 13. FASTAPI LAYER (thin: handlers are plain functions so they can be tested without a server)
# =====================================================================
def handle_preprocess(sessions: List[dict]) -> Dict[str, Any]:
    clean, quality, errors = preprocess_dataset(sessions)
    return {"clean_sessions": clean, "data_quality": quality, "errors": errors}


def handle_outcome(payload: dict) -> Dict[str, Any]:
    return record_outcome(payload.get("session_id", ""), payload.get("outcome", ""),
                          payload.get("action_taken", ""), payload.get("notes", ""), payload.get("primary_cause"))


try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(title="Friction AI Analyzer")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.post("/analyze")                                   # v1 endpoint (unchanged path and shape)
    def api_analyze(session: dict, use_llm: bool = False):
        try:
            return analyze_session(session, use_llm)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

    @app.post("/analyze/batch")                             # v1 endpoint (unchanged path and shape)
    def api_batch(sessions: List[dict], use_llm: bool = False):
        return analyze_all(sessions, use_llm)

    @app.post("/preprocess")                                # NEW: inspect cleaned data + quality report
    def api_preprocess(sessions: List[dict]):
        return handle_preprocess(sessions)

    @app.post("/outcome")                                   # NEW: feedback loop input
    def api_outcome(payload: dict):
        try:
            return handle_outcome(payload)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

    @app.get("/outcomes/summary")                           # NEW: feedback loop output
    def api_outcome_summary():
        return outcome_summary()
except ImportError:
    pass


# =====================================================================
# DEMO DATA  (first 6 sessions are the original v1 demo, unchanged)
# =====================================================================
DEMO = [
    {"session_id": "S1", "customer_id": "C101", "feedback": "My card payment failed twice, money deducted",
     "events": [{"type": "product_view", "ts": 0}, {"type": "add_to_cart", "ts": 40}, {"type": "checkout_start", "ts": 90},
                {"type": "payment_attempt", "ts": 120}, {"type": "payment_failed", "ts": 125},
                {"type": "payment_attempt", "ts": 150}, {"type": "payment_failed", "ts": 155}]},
    {"session_id": "S2", "customer_id": "C102", "feedback": "",
     "events": [{"type": "product_view", "ts": 0}, {"type": "add_to_cart", "ts": 30}, {"type": "view_cart", "ts": 60},
                {"type": "checkout_start", "ts": 90}, {"type": "shipping_cost_shown", "ts": 100, "meta": {"shipping_cost": 149}},
                {"type": "coupon_failed", "ts": 130}, {"type": "remove_from_cart", "ts": 160}]},
    {"session_id": "S3", "customer_id": "C103", "feedback": "Not sure about the size, description unclear",
     "events": [{"type": "product_view", "ts": 0}, {"type": "size_chart_view", "ts": 20}, {"type": "review_read", "ts": 50},
                {"type": "review_read", "ts": 80}, {"type": "product_view", "ts": 110}, {"type": "product_view", "ts": 140},
                {"type": "product_view", "ts": 170}]},
    {"session_id": "S4", "customer_id": "C104", "feedback": "",
     "events": [{"type": "product_view", "ts": 0}, {"type": "add_to_cart", "ts": 20}, {"type": "delivery_check", "ts": 50},
                {"type": "delivery_check", "ts": 80}]},
    {"session_id": "S5", "customer_id": "C105", "feedback": "Order not received, need refund",
     "events": [{"type": "purchase", "ts": 0}, {"type": "order_delayed", "ts": 5000}, {"type": "support_chat", "ts": 5100}]},
    {"session_id": "S6", "customer_id": "C106", "feedback": "",
     "events": [{"type": "product_view", "ts": 0}, {"type": "add_to_cart", "ts": 30}, {"type": "checkout_start", "ts": 60},
                {"type": "payment_attempt", "ts": 90}, {"type": "purchase", "ts": 100}]},
    # --- new demo sessions ---
    # S7: MESSY data (duplicate event, missing timestamp, missing customer id, noisy feedback)
    {"session_id": "S7", "customer_id": None, "feedback": "  DELIVERY is   TOO LATE!!!  \U0001F621 ",
     "events": [{"type": "product_view", "ts": "2026-09-30T10:00:00Z", "meta": {"price": 1999}},
                {"type": "add_to_cart", "ts": "2026-09-30T10:00:40Z", "meta": {"price": 1999}},
                {"type": "delivery_check", "ts": "2026-09-30T10:01:00Z", "meta": {"delivery_days": 8}},
                {"type": "delivery_check", "ts": "2026-09-30T10:01:00Z", "meta": {"delivery_days": 8}},
                {"type": "delivery_check", "ts": None, "meta": {"delivery_days": 8}},
                {"type": "", "ts": 5}]},
    # S8: friction but still purchased (payment failed once, retried, bought)
    {"session_id": "S8", "customer_id": "C108", "feedback": "",
     "events": [{"type": "product_view", "ts": 0}, {"type": "add_to_cart", "ts": 20}, {"type": "checkout_start", "ts": 50},
                {"type": "payment_attempt", "ts": 80}, {"type": "payment_failed", "ts": 85},
                {"type": "payment_attempt", "ts": 110}, {"type": "purchase", "ts": 118}]},
]


if __name__ == "__main__":
    report = analyze_all(DEMO)
    print(f"{'ID':<4}| {'STATUS':<25}| {'STAGE':<19}| {'PRIMARY CAUSE':<33}| CONF  | RISK")
    for r in report["results"]:
        print(f"{r['session_id']:<4}| {r['status']:<25}| {r['journey_stage']:<19}| {r['cause_label']:<33}| "
              f"{r['confidence']:<5} | {r['risk_score']} ({r['risk_level']})")
    print("\nDATASET SUMMARY:", json.dumps(report["summary"], indent=2))
    print("\nDATA QUALITY REPORT:", json.dumps(report["data_quality"], indent=2))
    print("\nFULL ANALYSIS OF S1 (features and journey trimmed for readability):")
    sample = dict(report["results"][0])
    sample["journey"] = {k: sample["journey"][k] for k in ("last_meaningful_stage", "sequence", "ended_after_friction")}
    print(json.dumps(sample, indent=2))


# =====================================================================
# BACKEND BRIDGE ADAPTER (Member 1 <-> Member 3)
# =====================================================================
_EVENT_MAP = {
    "compare_products": "compare",
    "shipping_shown": "shipping_cost_shown",
    "order_placed": "purchase",
    "exit": "session_exit",
    "cart_abandoned": "session_exit",
}

def analyze(analysis: dict, events: list[dict]) -> dict:
    """
    Adapter used by app.ai_bridge.
    Converts Member-1 backend events into Member-3's session contract,
    runs the tested rule-based AI/ML analyzer, and returns the compact
    shape expected by the backend/frontend.
    """
    raw_events = []
    feedback_parts = []

    for e in events or []:
        event_type = _EVENT_MAP.get(e.get("event_type"), e.get("event_type"))
        meta = e.get("metadata") or {}
        raw_events.append({
            "type": event_type,
            "ts": e.get("timestamp"),
            "meta": meta,
        })
        if isinstance(meta, dict):
            text = meta.get("text") or meta.get("topic")
            if text:
                feedback_parts.append(str(text))

    session = {
        "session_id": analysis.get("session_id", "UNKNOWN_SESSION"),
        "customer_id": analysis.get("customer_id", "UNKNOWN_CUSTOMER"),
        "events": raw_events,
        "feedback": " ".join(feedback_parts),
    }

    result = analyze_session(session)

    cause_map = {
        "PAYMENT_FAILURE": "payment_failure",
        "DELIVERY_UNCERTAINTY": "delivery_uncertainty",
        "UNCLEAR_PRODUCT_INFO": "product_info_gap",
        "PRICE_SHOCK": "price_shock",
        "POOR_RECOMMENDATIONS": "product_info_gap",
        "CHECKOUT_COMPLEXITY": "checkout_complexity",
        "POST_PURCHASE_ISSUE": "post_purchase_issue",
        "NONE": None,
    }

    primary = result.get("primary_cause", "NONE")
    evidence = result.get("evidence", [])
    recommendation = result.get("recommendation", {}).get(
        "action", "No action needed"
    )

    return {
        "cause": result.get("cause_label", "No significant friction detected"),
        "friction_type": cause_map.get(primary),
        "evidence": evidence,
        "confidence": round((float(result.get("confidence", 0)) / 100.0) if float(result.get("confidence", 0)) > 1 else float(result.get("confidence", 0)), 3),
        "recommendation": recommendation,
        "source": "member3-rules",
        "risk_score": result.get("risk_score", 0),
        "risk_level": result.get("risk_level", "LOW"),
        "explanation": result.get("explanation", ""),
    }
