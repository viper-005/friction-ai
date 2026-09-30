import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Brain,
  CheckCircle,
  DollarSign,
  RefreshCw,
  Users,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import "../dashboard.css";

const API = "http://localhost:8000";

const fallbackSummary = {
  total_sessions: 307,
  abandoned: 97,
  conversion_rate: 0.684,
  friction_counts: {
    payment_failure: 32,
    delivery_uncertainty: 24,
    product_info_gap: 19,
    price_shock: 14,
    post_purchase_issue: 11,
  },
  funnel: [
    { stage: "Viewed product", count: 307 },
    { stage: "Added to cart", count: 226 },
    { stage: "Started checkout", count: 158 },
    { stage: "Order placed", count: 110 },
  ],
  high_risk_customers: 42,
  revenue_at_risk: 482750,
};

function Dashboard() {
  const [summary, setSummary] = useState(fallbackSummary);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [summaryResponse, customerResponse] =
        await Promise.all([
          fetch(`${API}/friction/summary`),
          fetch(`${API}/customers?min_risk=40`),
        ]);

      if (summaryResponse.ok) {
        setSummary(await summaryResponse.json());
      }

      if (customerResponse.ok) {
        setCustomers(await customerResponse.json());
      }
    } catch (error) {
      console.log("Using demo data:", error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const frictionLabels = {
    payment_failure: "Payment Failure",
    delivery_uncertainty: "Delivery Uncertainty",
    product_info_gap: "Product Information",
    price_shock: "Price Shock",
    post_purchase_issue: "Post-Purchase",
  };

  const frictionEntries = Object.entries(
    summary.friction_counts || {}
  );

  return (
    <div className="dashboard-page">

      {/* HEADER */}

      <div className="dashboard-header">

        <div>
          <div className="section-label">
            AI OPERATIONS CENTER
          </div>

          <h1>Customer Journey Intelligence</h1>

          <p>
            Detect friction. Understand why. Recover customers.
          </p>
        </div>

        <button
          className="refresh-button"
          onClick={loadData}
        >
          <RefreshCw size={17} />
          Refresh
        </button>

      </div>

      {/* STATUS */}

      <div className="system-status">
        <span className="live-dot" />
        FrictionAI Engine Active
        <span className="status-divider" />
        Behavioral analysis running
      </div>

      {/* STATS */}

      <div className="stats-grid">

        <div className="stat-card">
          <div className="stat-icon blue">
            <Users size={21} />
          </div>

          <div>
            <span>Total Sessions</span>
            <strong>
              {summary.total_sessions?.toLocaleString()}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon green">
            <CheckCircle size={21} />
          </div>

          <div>
            <span>Conversion Rate</span>
            <strong>
              {(summary.conversion_rate * 100).toFixed(1)}%
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon red">
            <XCircle size={21} />
          </div>

          <div>
            <span>Abandoned</span>
            <strong>{summary.abandoned}</strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon orange">
            <AlertTriangle size={21} />
          </div>

          <div>
            <span>High Risk</span>
            <strong>{summary.high_risk_customers}</strong>
          </div>
        </div>

      </div>

      {/* MAIN GRID */}

      <div className="dashboard-grid">

        {/* FUNNEL */}

        <section className="dashboard-card funnel-card">

          <div className="card-header">
            <div>
              <span className="card-label">
                CUSTOMER JOURNEY
              </span>
              <h2>Conversion Funnel</h2>
            </div>
          </div>

          <div className="funnel">

            {(summary.funnel || []).map((item, index) => {

              const first =
                summary.funnel?.[0]?.count || 1;

              const width =
                Math.max(
                  25,
                  (item.count / first) * 100
                );

              return (
                <div
                  className="funnel-row"
                  key={item.stage}
                >

                  <div className="funnel-label">
                    <span>{item.stage}</span>
                    <strong>{item.count}</strong>
                  </div>

                  <div className="funnel-track">
                    <div
                      className="funnel-bar"
                      style={{ width: `${width}%` }}
                    />
                  </div>

                </div>
              );
            })}

          </div>

        </section>

        {/* FRICTION */}

        <section className="dashboard-card">

          <div className="card-header">
            <div>
              <span className="card-label">
                AI DETECTION
              </span>

              <h2>Top Friction Points</h2>
            </div>

            <Brain size={22} className="cyan-icon" />
          </div>

          <div className="friction-list">

            {frictionEntries.map(([key, value]) => {

              const total = frictionEntries.reduce(
                (sum, [, amount]) => sum + amount,
                0
              );

              const percentage =
                total > 0
                  ? Math.round((value / total) * 100)
                  : 0;

              return (
                <div
                  className="friction-row"
                  key={key}
                >

                  <div className="friction-info">
                    <span>
                      {frictionLabels[key] || key}
                    </span>

                    <strong>{percentage}%</strong>
                  </div>

                  <div className="friction-track">
                    <div
                      className="friction-bar"
                      style={{
                        width: `${percentage}%`,
                      }}
                    />
                  </div>

                </div>
              );
            })}

          </div>

        </section>

      </div>

      {/* REVENUE */}

      <div className="revenue-card">

        <div className="revenue-icon">
          <DollarSign size={25} />
        </div>

        <div>
          <span>Revenue potentially at risk</span>

          <strong>
            ₹{Number(
              summary.revenue_at_risk || 0
            ).toLocaleString("en-IN")}
          </strong>
        </div>

        <div className="revenue-text">
          Customers with detected journey friction
          represent potential recovery opportunities.
        </div>

      </div>

      {/* CUSTOMERS */}

      <section className="dashboard-card customers-card">

        <div className="card-header">

          <div>
            <span className="card-label">
              PRIORITY QUEUE
            </span>

            <h2>Customers Requiring Attention</h2>
          </div>

          <Link
            to="/customers"
            className="view-all"
          >
            View all
            <ArrowRight size={16} />
          </Link>

        </div>

        <div className="customer-table">

          <div className="table-header">
            <span>Customer</span>
            <span>Risk</span>
            <span>Friction</span>
            <span>Action</span>
          </div>

          {customers.length > 0 ? (

            customers.slice(0, 6).map((customer) => (

              <div
                className="table-row"
                key={customer.customer_id}
              >

                <span className="customer-id">
                  {customer.customer_id}
                </span>

                <span
                  className={`risk-badge ${
                    customer.risk_score >= 60
                      ? "high"
                      : "medium"
                  }`}
                >
                  {customer.risk_score >= 60
                    ? "HIGH"
                    : "MEDIUM"}
                  <b>{customer.risk_score}</b>
                </span>

                <span>
                  {frictionLabels[
                    customer.top_friction
                  ] || customer.top_friction}
                </span>

                <Link
                  to={`/customer/${customer.customer_id}`}
                  className="analyze-link"
                >
                  Analyze
                  <ArrowRight size={15} />
                </Link>

              </div>

            ))

          ) : (

            <div className="demo-customer-row">

              <span className="customer-id">
                C-DEMO-001
              </span>

              <span className="risk-badge high">
                HIGH <b>78</b>
              </span>

              <span>Payment Failure</span>

              <Link
                to="/customer/demo"
                className="analyze-link"
              >
                Analyze
                <ArrowRight size={15} />
              </Link>

            </div>

          )}

        </div>

      </section>

    </div>
  );
}

export default Dashboard;