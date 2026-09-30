import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Brain,
  CheckCircle,
  CircleAlert,
  Zap,
} from "lucide-react";

import { Link, useParams } from "react-router-dom";

const API = "http://localhost:8000";

function CustomerDetails() {
  const { id } = useParams();
  const LIVE_SESSION_ID = "S0063";

  const [journey, setJourney] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [recovered, setRecovered] = useState(false);

  useEffect(() => {
       async function load() {
          try {
             const journeyResponse = await fetch(
              `${API}/customers/CB7ED038E/journey`
            );

              if (journeyResponse.ok) {
               const journeyData = await journeyResponse.json();
              setJourney(journeyData);
            }

              const analysisResponse = await fetch(
              `${API}/analyze/${LIVE_SESSION_ID}`,
             {
               method: "POST",
                }
             );

              if (analysisResponse.ok) {
              const analysisData =
              await analysisResponse.json();

             setAnalysis(analysisData);
             }

             } catch (error) {
              console.error(
             "Live analysis unavailable:",
               error
           );
        }
     }

     load();
  }, []);
  const demo = {
    customer_id: "C-DEMO-001",
    risk_score: 78,
    friction: "Payment Failure",
    cause: "Repeated payment failures",
    confidence: 94,
    evidence: [
      "Two payment failures occurred during checkout",
      "Customer retried payment immediately",
      "Customer abandoned the cart after the second failure",
    ],
    recommendation:
      "Offer an alternative payment method and assisted checkout.",
    events: [
      ["Product viewed", "10:41:02", "normal"],
      ["Product compared", "10:42:18", "normal"],
      ["Added to cart", "10:43:04", "normal"],
      ["Checkout started", "10:44:11", "normal"],
      ["Payment failed", "10:44:32", "danger"],
      ["Payment failed", "10:45:07", "danger"],
      ["Cart abandoned", "10:45:42", "danger"],
    ],
  };

  let data = demo;

if (analysis) {
  data = {
    customer_id: "CB7ED038E",
    risk_score: analysis.risk_score,
    friction: analysis.friction_type,
    cause: analysis.cause,
    confidence: Math.round(
      analysis.confidence * 100
    ),
    evidence: analysis.evidence || [],
    recommendation:
      analysis.recommendation,
    events: demo.events,
  };
}

  const handleRecovery = async () => {
  try {
    const response = await fetch(
      "http://localhost:8000/actions/trigger",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          customer_id: "CB7ED038",
          session_id: "S0063",
          action_type: "payment_recovery",
          reason: "Payment gateway/UPI/card failures blocking checkout",
        }),
      }
    );

    const result = await response.json();

    console.log("Recovery action:", result);

    setRecovered(true);

    alert("✅ Recovery action triggered successfully!");
  } catch (error) {
    console.error("Recovery failed:", error);
    alert("❌ Recovery action failed");
  }
};
  return (
    <div className="customer-detail-page">

      <Link
        to="/dashboard"
        className="back-link"
      >
        <ArrowLeft size={18} />
        Back to Dashboard
      </Link>

      <div className="customer-detail-header">

        <div>
          <span className="section-label">
            CUSTOMER JOURNEY ANALYSIS
          </span>

          <h1>{data.customer_id}</h1>

          <p>
            AI-powered friction investigation
          </p>
        </div>

        <div className="risk-score-card">

          <span>FRICTION SCORE</span>

          <strong>{data.risk_score}</strong>

          <b>HIGH RISK</b>

        </div>

      </div>

      <div className="journey-layout">

        {/* JOURNEY */}

        <section className="dashboard-card">

          <div className="card-header">

            <div>
              <span className="card-label">
                BEHAVIORAL TIMELINE
              </span>

              <h2>Customer Journey</h2>
            </div>

          </div>

          <div className="journey-timeline">

            {data.events.map(
              ([event, time, type], index) => (

                <div
                  className="timeline-item"
                  key={`${event}-${index}`}
                >

                  <div className="timeline-time">
                    {time}
                  </div>

                  <div
                    className={`timeline-dot ${
                      type === "danger"
                        ? "danger-dot"
                        : ""
                    }`}
                  />

                  <div
                    className={`timeline-content ${
                      type === "danger"
                        ? "danger-event"
                        : ""
                    }`}
                  >
                    {type === "danger" ? (
                      <CircleAlert size={17} />
                    ) : (
                      <CheckCircle size={17} />
                    )}

                    <span>{event}</span>
                  </div>

                </div>
              )
            )}

          </div>

        </section>

        {/* AI */}

        <section className="dashboard-card ai-analysis-card">

          <div className="ai-heading">
            <div className="ai-brain">
              <Brain size={23} />
            </div>

            <div>
              <span className="card-label">
                AI ANALYSIS
              </span>

              <h2>Why did this happen?</h2>
            </div>
          </div>

          <div className="ai-friction">

            <span>DETECTED FRICTION</span>

            <strong>
              {data.friction}
            </strong>

          </div>

          <div className="confidence">

            <div>
              <span>AI Confidence</span>
              <strong>
                {data.confidence}%
              </strong>
            </div>

            <div className="confidence-track">
              <div
                style={{
                  width: `${data.confidence}%`,
                }}
              />
            </div>

          </div>

          <div className="ai-section">

            <span>LIKELY CAUSE</span>

            <p>{data.cause}</p>

          </div>

          <div className="ai-section">

            <span>SUPPORTING EVIDENCE</span>

            <ul>
              {data.evidence.map(
                (item, index) => (
                  <li key={index}>
                    <CheckCircle size={16} />
                    {item}
                  </li>
                )
              )}
            </ul>

          </div>

          <div className="recommendation">

            <div className="recommendation-icon">
              <Zap size={19} />
            </div>

            <div>
              <span>
                RECOMMENDED RECOVERY
              </span>

              <p>
                {data.recommendation}
              </p>
            </div>

          </div>

          <button
            className="recovery-button"
            onClick={handleRecovery}
            disabled={recovered}
          >
            {recovered ? (
              <>
                <CheckCircle size={19} />
                Recovery Triggered
              </>
            ) : (
              <>
                <Zap size={19} />
                Trigger Recovery
              </>
            )}
          </button>

        </section>

      </div>

    </div>
  );
}

export default CustomerDetails;