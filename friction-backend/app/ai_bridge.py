"""Bridge to Member 3's AI analyzer.
Member 3: create app/ai_analyzer.py with  analyze(session: dict, events: list[dict]) -> dict
returning {cause, evidence: [str], confidence: float 0-1, recommendation: str}.
If missing or it raises/times out, we fall back to a deterministic analysis so the demo never breaks."""
import concurrent.futures

try:
    from . import ai_analyzer  # type: ignore
except Exception:
    ai_analyzer = None

RECOMMEND = {
    "payment_failure": "Offer alternate payment (card/COD/wallet), send a retry link, alert payments team about gateway errors",
    "delivery_uncertainty": "Show estimated delivery date on product page; send WhatsApp with delivery ETA and free-delivery nudge",
    "price_shock": "Show shipping cost earlier; send a free-shipping coupon or bundle suggestion",
    "product_info_gap": "Trigger assisted chat with comparison table; send personalized recommendations",
    "post_purchase_issue": "Proactive apology with tracking update; escalate to support with priority; goodwill voucher",
}


def fallback(analysis: dict) -> dict:
    if not analysis["frictions"]:
        return dict(cause="No significant friction detected", evidence=[], confidence=0.9,
                    recommendation="No action needed", source="rules")
    top = analysis["frictions"][0]
    conf = round(min(0.95, 0.55 + 0.4 * top["severity"] + 0.05 * (len(analysis["frictions"]) - 1)), 2)
    return dict(cause=top["business_cause"], friction_type=top["type"],
                evidence=[f["evidence"] for f in analysis["frictions"]],
                confidence=conf, recommendation=RECOMMEND[top["type"]], source="rules")


def analyze(analysis: dict, events: list[dict]) -> dict:
    if ai_analyzer is not None:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                res = ex.submit(ai_analyzer.analyze, analysis, events).result(timeout=15)
            res["source"] = "ai"
            return res
        except Exception as e:  # LLM slow/broken -> deterministic fallback
            out = fallback(analysis)
            out["note"] = f"AI unavailable ({type(e).__name__}), used rules"
            return out
    return fallback(analysis)
