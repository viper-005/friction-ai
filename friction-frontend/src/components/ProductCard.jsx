import { Link } from "react-router-dom";
import { Star, ShoppingCart } from "lucide-react";

function ProductCard({ product, onAddToCart }) {
  return (
    <div className="product-card">
      <img
        src={product.image}
        alt={product.name}
        className="product-image"
      />

      <div className="product-info">
        <span className="product-category">
          {product.category}
        </span>

        <h3>{product.name}</h3>

        <div className="rating">
          <Star size={16} fill="currentColor" />
          <span>{product.rating}</span>
        </div>

        <p className="product-description">
          {product.description}
        </p>

        <div className="product-bottom">
          <strong>₹{product.price.toLocaleString("en-IN")}</strong>

          <div className="product-actions">
            <Link
              to={`/product/${product.id}`}
              className="view-btn"
            >
              View
            </Link>

            <button
              className="cart-btn"
              onClick={() => onAddToCart(product)}
              title="Add to cart"
            >
              <ShoppingCart size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProductCard;