# Journey Friction Detection - Backend (Member 1)

## Run
```
pip install -r requirements.txt
python data/generate_sample.py        # only if you don't have Member 4's data yet
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000/docs for interactive API docs (share this URL with Members 2 & 3).

## Data contract for Member 4 (`data/events.csv`)
Columns: `customer_id,timestamp(ISO),event_type,metadata(JSON string, optional),session_id(optional)`

| event_type | useful metadata |
|---|---|
| product_view, compare_products | product_id |
| add_to_cart | product_id, cart_value |
| checkout_start | - |
| delivery_check | pincode, dwell_seconds |
| shipping_shown | shipping_cost, cart_value |
| payment_attempt / payment_failed | method (UPI/card), reason |
| order_placed | order_id |
| support_ticket / review_negative | topic or text |
| exit | - |

After replacing the CSV, call `POST /reload`.

## Endpoints
- `GET /customers?min_risk=60&friction=payment_failure` - list, sorted by risk
- `GET /customers/{id}/journey` - sessions with ordered events, friction points flagged per event
- `GET /sessions`, `GET /friction/summary` - chart data (friction counts, funnel, conversion, revenue at risk)
- `POST /analyze/{session_id}` - `{cause, evidence[], confidence, recommendation, source}`
- `POST /actions/trigger` body `{"session_id":"S0010","channel":"whatsapp"}`
- `POST /actions/auto` - fires recovery for all sessions with risk >= `RISK_THRESHOLD` (default 60)
- `GET /actions/log`

## Plugging in Member 3's AI
Create `app/ai_analyzer.py` with `analyze(session: dict, events: list[dict]) -> dict`
returning `{cause, evidence: [str], confidence: 0-1, recommendation}`.
It is picked up automatically; on error/timeout (15s) the rule-based fallback answers, so the demo never breaks.

## Friction rules (app/pipeline.py)
payment_failure (>=2 failed payments), delivery_uncertainty (repeat/long pincode checks, no order),
price_shock (shipping >= Rs50 or 8% of cart, then exit), product_info_gap (>=4 views/compares, no cart),
post_purchase_issue (ticket / negative review). Tune thresholds there.
Risk score = strongest friction + 30% of the others, capped at 100. Customer IDs are SHA-256 hashed.
