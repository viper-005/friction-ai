import { Link } from "react-router-dom";
import { ShoppingCart, Activity } from "lucide-react";

function Navbar({ cartCount }) {
  return (
    <nav className="navbar">
      <Link to="/" className="brand">
        <div className="brand-icon">
          <Activity size={22} />
        </div>

        <div>
          <div className="brand-name">FrictionMart</div>
          <div className="brand-tagline">
            Powered by FrictionAI
          </div>
        </div>
      </Link>

      <div className="nav-links">
        <Link to="/">Home</Link>

        <Link to="/dashboard" className="ai-link">
          AI Dashboard
        </Link>

        <Link to="/cart" className="cart-link">
          <ShoppingCart size={20} />
          <span>Cart</span>

          {cartCount > 0 && (
            <span className="cart-count">
              {cartCount}
            </span>
          )}
        </Link>
      </div>
    </nav>
  );
}

export default Navbar;