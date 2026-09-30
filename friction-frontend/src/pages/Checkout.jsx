import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CreditCard,
  Lock,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { trackEvent } from "../services/tracker";

function Checkout({ cart, clearCart }) {
  const navigate = useNavigate();

  const [paymentAttempts, setPaymentAttempts] = useState(0);
  const [paymentFailed, setPaymentFailed] = useState(false);

  const total = cart.reduce(
    (sum, item) => sum + item.price * item.quantity,
    0
  );

  const handlePayment = () => {
    const nextAttempt = paymentAttempts + 1;

    setPaymentAttempts(nextAttempt);
    setPaymentFailed(true);

    trackEvent("payment_failed", {
      attempt: nextAttempt,
      amount: total,
      payment_method: "UPI",
      reason: "bank_timeout",
    });
  };

  const handleAbandon = () => {
    trackEvent("cart_abandoned", {
      amount: total,
      payment_attempts: paymentAttempts,
    });

    navigate("/");
  };

  if (cart.length === 0) {
    return (
      <div className="empty-cart">
        <h2>No items to checkout</h2>
        <Link to="/" className="primary-action">
          Go Shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="checkout-page">

      <Link to="/cart" className="back-link">
        <ArrowLeft size={18} />
        Back to cart
      </Link>

      <div className="page-heading">
        <span className="section-label">SECURE CHECKOUT</span>
        <h1>Complete your purchase</h1>
      </div>

      <div className="checkout-layout">

        <div className="payment-card">

          <div className="secure-label">
            <Lock size={16} />
            Secure encrypted payment
          </div>

          <h2>Payment Method</h2>

          <div className="payment-method active">
            <CreditCard size={22} />

            <div>
              <strong>UPI Payment</strong>
              <span>Fast & secure</span>
            </div>

            <div className="selected-dot" />
          </div>

          <button
            className="pay-button"
            onClick={handlePayment}
          >
            Pay ₹{total.toLocaleString("en-IN")}
          </button>

          {paymentFailed && (
            <div className="payment-error">

              <XCircle size={25} />

              <div>
                <strong>Payment failed</strong>

                <p>
                  We couldn't process your payment.
                  Please try again.
                </p>

                <small>
                  Attempt #{paymentAttempts} • Bank timeout
                </small>
              </div>

            </div>
          )}

          {paymentFailed && (
            <button
              className="abandon-button"
              onClick={handleAbandon}
            >
              Leave checkout
            </button>
          )}

          <div className="trust-row">
            <ShieldCheck size={18} />
            Your payment information is protected.
          </div>

        </div>

        <div className="checkout-summary">

          <h2>Order Summary</h2>

          {cart.map((item) => (
            <div
              className="checkout-product"
              key={item.id}
            >
              <img
                src={item.image}
                alt={item.name}
              />

              <div>
                <strong>{item.name}</strong>
                <span>
                  Qty: {item.quantity}
                </span>
              </div>

              <strong>
                ₹{(
                  item.price * item.quantity
                ).toLocaleString("en-IN")}
              </strong>
            </div>
          ))}

          <div className="summary-divider" />

          <div className="summary-total">
            <span>Total</span>
            <strong>
              ₹{total.toLocaleString("en-IN")}
            </strong>
          </div>

        </div>

      </div>
    </div>
  );
}

export default Checkout;