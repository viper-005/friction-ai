"""Core logic: load -> anonymize -> sessionize -> detect friction -> score."""
import csv, hashlib, json
from collections import defaultdict
from datetime import datetime, timedelta

SALT = "hackathon-salt"          # change for real use
SESSION_GAP = timedelta(minutes=30)

# weight = risk points at full severity; score = strongest friction + 30% of the others (cap 100)
WEIGHTS = {
    "payment_failure": 90,
    "delivery_uncertainty": 75,
    "price_shock": 70,
    "product_info_gap": 55,
    "post_purchase_issue": 85,
}
BUSINESS_CAUSE = {
    "payment_failure": "Payment gateway/UPI/card failures blocking checkout",
    "delivery_uncertainty": "Unclear delivery date or serviceability at pincode step",
    "price_shock": "Shipping/extra charges revealed late in checkout",
    "product_info_gap": "Insufficient product info or weak recommendations",
    "post_purchase_issue": "Order/delivery problem hurting loyalty after purchase",
}


def anonymize(cid: str) -> str:
    return "C" + hashlib.sha256((SALT + cid).encode()).hexdigest()[:8].upper()


def load_events(path: str) -> list[dict]:
    """CSV columns: customer_id,timestamp,event_type,metadata(JSON, optional),session_id(optional)"""
    events = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            meta = json.loads(r["metadata"]) if r.get("metadata") else {}
            events.append({
                "customer_id": anonymize(r["customer_id"]),
                "timestamp": datetime.fromisoformat(r["timestamp"]),
                "event_type": r["event_type"].strip(),
                "metadata": meta,
                "session_id": r.get("session_id") or None,
            })
    return events


def sessionize(events: list[dict]) -> dict[str, list[dict]]:
    """Group by customer; new session after 30 min of inactivity (unless session_id given)."""
    by_cust = defaultdict(list)
    for e in events:
        by_cust[e["customer_id"]].append(e)
    sessions, n = {}, 0
    for cid, evs in by_cust.items():
        evs.sort(key=lambda e: e["timestamp"])
        current, last = None, None
        for e in evs:
            if e["session_id"]:
                sid = e["session_id"]
            else:
                if last is None or e["timestamp"] - last > SESSION_GAP:
                    n += 1
                    current = f"S{n:04d}"
                sid = current
            e["session_id"] = sid
            sessions.setdefault(sid, []).append(e)
            last = e["timestamp"]
    return sessions


# ---------------- detectors: each returns a dict or None ----------------
def _idx(evs, *types):
    return [i for i, e in enumerate(evs) if e["event_type"] in types]


def _ordered(evs, types):
    return [i for i, e in enumerate(evs) if e["event_type"] in types]


def d_payment(evs):
    fails = _idx(evs, "payment_failed")
    if len(fails) < 2:
        return None
    recovered = bool(_idx(evs, "order_placed"))
    span = (evs[fails[-1]]["timestamp"] - evs[fails[0]]["timestamp"]).seconds // 60
    methods = sorted({evs[i]["metadata"].get("method", "unknown") for i in fails})
    reasons = sorted({evs[i]["metadata"].get("reason", "") for i in fails if evs[i]["metadata"].get("reason")})
    sev = min(1.0, len(fails) / 4) * (0.5 if recovered else 1.0)
    ev = f"{len(fails)} failed payments in {span} min via {', '.join(methods)}"
    if reasons:
        ev += f" (reason: {', '.join(reasons)})"
    ev += "; customer eventually paid" if recovered else "; no order placed"
    return dict(severity=sev, evidence=ev, event_indices=fails)


def d_delivery(evs):
    checks = _idx(evs, "delivery_check")
    if not checks or _idx(evs, "order_placed"):
        return None
    dwell = max(evs[i]["metadata"].get("dwell_seconds", 0) for i in checks)
    if len(checks) < 2 and dwell < 20:
        return None
    sev = min(1.0, 0.4 + 0.1 * len(checks) + dwell / 120)
    return dict(severity=sev, indices=checks, event_indices=checks,
                evidence=f"{len(checks)} pincode/delivery checks, longest dwell {dwell}s, then left without ordering")


def d_price(evs):
    ship = _idx(evs, "shipping_shown")
    if not ship or _idx(evs, "order_placed"):
        return None
    m = evs[ship[-1]]["metadata"]
    cost, cart = m.get("shipping_cost", 0), m.get("cart_value", 0)
    pct = cost / cart * 100 if cart else 0
    if cost < 50 and pct < 8:
        return None
    sev = min(1.0, 0.5 + pct / 40)
    return dict(severity=sev, event_indices=ship,
                evidence=f"Cart abandoned after shipping charge of Rs {cost} ({pct:.0f}% of Rs {cart} cart) was shown")


def d_info(evs):
    views = _idx(evs, "product_view", "compare_products")
    products = {evs[i]["metadata"].get("product_id") for i in views}
    if len(views) < 4 or _idx(evs, "add_to_cart", "order_placed"):
        return None
    sev = min(1.0, len(views) / 8)
    return dict(severity=sev, event_indices=views,
                evidence=f"{len(views)} product/compare views across {len(products)} products with no add-to-cart")


def d_post(evs):
    idx = _idx(evs, "support_ticket", "review_negative")
    if not idx:
        return None
    m = evs[idx[0]]["metadata"]
    what = m.get("topic") or m.get("text") or "issue reported"
    return dict(severity=0.9, event_indices=idx,
                evidence=f"{len(idx)} post-purchase complaint event(s): {what}")


DETECTORS = {
    "payment_failure": d_payment, "delivery_uncertainty": d_delivery,
    "price_shock": d_price, "product_info_gap": d_info, "post_purchase_issue": d_post,
}


def analyze_session(sid: str, evs: list[dict]) -> dict:
    frictions = []
    for name, fn in DETECTORS.items():
        r = fn(evs)
        if r:
            r.pop("indices", None)
            frictions.append(dict(type=name, business_cause=BUSINESS_CAUSE[name], **r))
    frictions.sort(key=lambda f: -WEIGHTS[f["type"]] * f["severity"])
    pts = [WEIGHTS[f["type"]] * f["severity"] for f in frictions]
    score = min(100, round((pts[0] + 0.3 * sum(pts[1:])) if pts else 0))
    if _idx(evs, "order_placed"):
        outcome = "converted"
    elif _idx(evs, "support_ticket", "review_negative"):
        outcome = "post_purchase"
    else:
        outcome = "abandoned"
    return dict(session_id=sid, customer_id=evs[0]["customer_id"],
                start=evs[0]["timestamp"].isoformat(), outcome=outcome,
                risk_score=score, top_friction=frictions[0]["type"] if frictions else None,
                frictions=frictions, n_events=len(evs))


def build_all(path: str):
    sessions = sessionize(load_events(path))
    analyses = {sid: analyze_session(sid, evs) for sid, evs in sessions.items()}
    customers = {}
    for a in analyses.values():
        c = customers.setdefault(a["customer_id"], dict(customer_id=a["customer_id"], sessions=[], risk_score=0, top_friction=None))
        c["sessions"].append(a["session_id"])
        if a["risk_score"] >= c["risk_score"]:
            c["risk_score"], c["top_friction"] = a["risk_score"], a["top_friction"]
    return sessions, analyses, customers


def serialize_events(evs, frictions):
    flagged = {}
    for f in frictions:
        for i in f["event_indices"]:
            flagged.setdefault(i, []).append(f["type"])
    return [dict(step=i, timestamp=e["timestamp"].isoformat(), event_type=e["event_type"],
                 metadata=e["metadata"], friction=flagged.get(i, [])) for i, e in enumerate(evs)]
