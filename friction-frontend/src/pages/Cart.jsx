import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Minus,
  Plus,
  ShoppingBag,
  Trash2,
} from "lucide-react";

import { trackEvent } from "../services/tracker";

function Cart({
  cart,
  updateQuantity,
  removeFromCart,
}) {
  const total = cart.reduce(
    (sum, item) => sum + item.price * item.quantity,
    0
  );

  const handleCheckout = () => {
    trackEvent("checkout_start", {
      cart_value: total,
      item_count: cart.length,
    });
  };

  if (cart.length === 0) {
    return (
      <div className="empty-cart">
        <ShoppingBag size={55} />

        <h2>Your cart is empty</h2>

        <p>
          Add something to your cart and start shopping.
        </p>

        <Link to="/" className="primary-action">
          Continue Shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="cart-page">

      <Link to="/" className="back-link">
        <ArrowLeft size={18} />
        Continue Shopping
      </Link>

      <div className="page-heading">
        <span className="section-label">YOUR CART</span>
        <h1>Shopping Cart</h1>
      </div>

      <div className="cart-layout">

        <div className="cart-items">

          {cart.map((item) => (
            <div className="cart-item" key={item.id}>

              <img
                src={item.image}
                alt={item.name}
              />

              <div className="cart-item-info">

                <span>{item.category}</span>

                <h3>{item.name}</h3>

                <strong>
                  ₹{item.price.toLocaleString("en-IN")}
                </strong>

                <div className="quantity-controls">

                  <button
                    onClick={() =>
                      updateQuantity(
                        item.id,
                        item.quantity - 1
                      )
                    }
                  >
                    <Minus size={15} />
                  </button>

                  <span>{item.quantity}</span>

                  <button
                    onClick={() =>
                      updateQuantity(
                        item.id,
                        item.quantity + 1
                      )
                    }
                  >
                    <Plus size={15} />
                  </button>

                </div>

              </div>

              <button
                className="remove-button"
                onClick={() => {
                  removeFromCart(item.id);

                  trackEvent("remove_from_cart", {
                    product_id: item.id,
                    product_name: item.name,
                  });
                }}
              >
                <Trash2 size={18} />
              </button>

            </div>
          ))}

        </div>

        <div className="cart-summary">

          <h2>Order Summary</h2>

          <div className="summary-row">
            <span>Subtotal</span>
            <strong>
              ₹{total.toLocaleString("en-IN")}
            </strong>
          </div>

          <div className="summary-row">
            <span>Delivery</span>
            <strong>FREE</strong>
          </div>

          <div className="summary-divider" />

          <div className="summary-total">
            <span>Total</span>
            <strong>
              ₹{total.toLocaleString("en-IN")}
            </strong>
          </div>

          <Link
            to="/checkout"
            className="checkout-button"
            onClick={handleCheckout}
          >
            Proceed to Checkout
          </Link>

        </div>

      </div>
    </div>
  );
}

export default Cart;