import os
import csv
import json
from datetime import datetime
from collections import Counter
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import pipeline, ai_bridge, actions

DATA_PATH = os.getenv("EVENTS_CSV", "data/events.csv")
RISK_THRESHOLD = int(os.getenv("RISK_THRESHOLD", "60"))


class EventReq(BaseModel):
    customer_id: str = "DEMO-CUSTOMER-001"
    event_type: str
    timestamp: str | None = None
    metadata: dict = {}
    session_id: str | None = None


app = FastAPI(title="Journey Friction Detection API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STATE = {}


def load():
    s, a, c = pipeline.build_all(DATA_PATH)
    STATE.update(sessions=s, analyses=a, customers=c)


@app.on_event("startup")
def _startup():
    load()


@app.get("/health")
def health():
    return dict(status="ok", sessions=len(STATE["sessions"]), customers=len(STATE["customers"]))



@app.post("/events")
def ingest_event(req: EventReq):
    """
    Lightweight hackathon ingestion endpoint for the React demo.
    Appends one event using Member-4's CSV contract, then rebuilds the
    in-memory pipeline so the dashboard can see the event immediately.
    """
    event_type = req.event_type.strip()
    if event_type == "cart_abandoned":
        event_type = "exit"

    allowed = {
       "page_view",
       "search",
       "product_view",
       "compare_products",
       "add_to_cart",
       "remove_from_cart",
       "view_cart",
       "checkout_start",
       "delivery_check",
       "shipping_shown",
       "coupon_failed",

       # New friction events
       "login_failed",
       "otp_failed",
        "inventory_unavailable",

       "payment_attempt",
       "payment_failed",
       "order_placed",
       "support_ticket",
       "review_negative",
       "exit",
       "session_exit",
    }
    if event_type not in allowed:
        raise HTTPException(400, f"unsupported event_type: {event_type}")

    ts = req.timestamp or datetime.now().isoformat(timespec="seconds")
    row = [
        req.customer_id,
        ts,
        event_type,
        json.dumps(req.metadata or {}, separators=(",", ":")),
        req.session_id or "",
    ]

    os.makedirs(os.path.dirname(DATA_PATH) or ".", exist_ok=True)
    exists = os.path.exists(DATA_PATH)
    with open(DATA_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists or os.path.getsize(DATA_PATH) == 0:
            writer.writerow(["customer_id", "timestamp", "event_type", "metadata", "session_id"])
        writer.writerow(row)

    load()
    return {
        "ok": True,
        "event_type": event_type,
        "customer_id": req.customer_id,
        "session_id": req.session_id,
        "timestamp": ts,
        "dashboard_updated": True,
    }

@app.post("/reload")
def reload_data():
    """Call after Member 4 replaces data/events.csv."""
    load()
    return health()


@app.get("/customers")
def customers(min_risk: int = 0, friction: str | None = None):
    out = [c for c in STATE["customers"].values()
           if c["risk_score"] >= min_risk and (friction is None or c["top_friction"] == friction)]
    return sorted(out, key=lambda c: -c["risk_score"])


@app.get("/customers/{cid}/journey")
def journey(cid: str):
    c = STATE["customers"].get(cid)
    if not c:
        raise HTTPException(404, "customer not found")
    out = []
    for sid in c["sessions"]:
        a = STATE["analyses"][sid]
        out.append(dict(**a, events=pipeline.serialize_events(STATE["sessions"][sid], a["frictions"])))
    return dict(customer_id=cid, risk_score=c["risk_score"], sessions=out)


@app.get("/sessions")
def sessions(min_risk: int = 0):
    return sorted([a for a in STATE["analyses"].values() if a["risk_score"] >= min_risk],
                  key=lambda a: -a["risk_score"])


@app.get("/friction/summary")
def summary():
    an = list(STATE["analyses"].values())
    types = Counter(f["type"] for a in an for f in a["frictions"])
    abandoned = [a for a in an if a["outcome"] == "abandoned"]
    ev_types = Counter(e["event_type"] for evs in STATE["sessions"].values() for e in evs)

    # The legacy pipeline/friction objects were built around the original
    # five friction categories. The live demo also accepts the three new
    # event types, so make those categories visible in the dashboard summary
    # directly from the ingested session events.
    demo_friction_events = {
        "login_authentication": {"login_failed", "otp_failed"},
        "inventory_unavailable": {"inventory_unavailable"},
        "coupon_discount_failure": {"coupon_failed"},
    }

    for friction_type, event_names in demo_friction_events.items():
        affected_sessions = sum(
            any(e["event_type"] in event_names for e in evs)
            for evs in STATE["sessions"].values()
        )
        if affected_sessions:
            # Only add the live-event-derived category when the legacy
            # pipeline has not already produced it.
            types.setdefault(friction_type, affected_sessions)

    funnel = [dict(stage=s, count=len({e["session_id"] for evs in STATE["sessions"].values()
                                       for e in evs if e["event_type"] == k}))
              for s, k in [("Viewed product", "product_view"), ("Added to cart", "add_to_cart"),
                           ("Started checkout", "checkout_start"), ("Order placed", "order_placed")]]
    return dict(total_sessions=len(an), abandoned=len(abandoned),
                conversion_rate=round(1 - len(abandoned) / max(1, len(an)), 3),
                friction_counts=dict(types), funnel=funnel,
                high_risk_customers=sum(c["risk_score"] >= RISK_THRESHOLD for c in STATE["customers"].values()),
                revenue_at_risk=sum(_cart(sid) for sid, a in STATE["analyses"].items() if a["outcome"] == "abandoned"),
                event_counts=dict(ev_types))


def _cart(sid):
    vals = [e["metadata"].get("cart_value", 0) for e in STATE["sessions"][sid]]
    return max(vals) if vals else 0


@app.post("/analyze/{session_id}")
def analyze(session_id: str):
    a = STATE["analyses"].get(session_id)
    if not a:
        raise HTTPException(404, "session not found")
    evs = pipeline.serialize_events(STATE["sessions"][session_id], a["frictions"])
    return dict(session_id=session_id, risk_score=a["risk_score"], **ai_bridge.analyze(a, evs))


class ActionReq(BaseModel):
    session_id: str
    channel: str = "email"


@app.post("/actions/trigger")
def trigger(req: ActionReq):
    a = STATE["analyses"].get(req.session_id)
    if not a:
        raise HTTPException(404, "session not found")
    try:
        return actions.trigger(req.session_id, a["customer_id"], a["top_friction"], req.channel)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/actions/auto")
def auto():
    """Workflow trigger: fire recovery for every abandoned session over the risk threshold."""
    fired = [actions.trigger(sid, a["customer_id"], a["top_friction"], "whatsapp", auto=True)
             for sid, a in STATE["analyses"].items()
             if a["risk_score"] >= RISK_THRESHOLD and a["outcome"] != "converted"
             and not any(x["session_id"] == sid for x in actions.LOG)]
    return dict(threshold=RISK_THRESHOLD, fired=len(fired), actions=fired)


@app.get("/actions/log")
def action_log():
    return actions.LOG[::-1]
