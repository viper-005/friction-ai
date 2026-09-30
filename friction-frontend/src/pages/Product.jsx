import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  GitCompare,
  ShoppingCart,
  Star,
  Truck,
} from "lucide-react";

import { products } from "../data/products";
import { trackEvent } from "../services/tracker";

function Product({ addToCart }) {
  const { id } = useParams();

  const product = products.find((item) => item.id === id);

  useEffect(() => {
    if (product) {
      trackEvent("product_view", {
        product_id: product.id,
        product_name: product.name,
        category: product.category,
      });
    }
  }, [product]);

  if (!product) {
    return (
      <div className="not-found">
        <h2>Product not found</h2>

        <Link to="/">
          Back to shopping
        </Link>
      </div>
    );
  }

  const handleCompare = () => {
    trackEvent("product_compare", {
      product_id: product.id,
      product_name: product.name,
    });

    alert(
      "Product added to comparison.\n\nThis interaction is being tracked by FrictionAI."
    );
  };

  const handleAddToCart = () => {
    trackEvent("add_to_cart", {
      product_id: product.id,
      product_name: product.name,
      price: product.price,
    });

    addToCart(product);
  };

  return (
    <div className="product-page">

      <Link to="/" className="back-link">
        <ArrowLeft size={18} />
        Back to products
      </Link>

      <div className="product-detail">

        <div className="product-detail-image">
          <img
            src={product.image}
            alt={product.name}
          />
        </div>

        <div className="product-detail-info">

          <span className="product-category">
            {product.category}
          </span>

          <h1>{product.name}</h1>

          <div className="detail-rating">
            <Star
              size={18}
              fill="currentColor"
            />

            <strong>{product.rating}</strong>

            <span>Customer rating</span>
          </div>

          <p className="detail-description">
            {product.description}
          </p>

          <div className="price-large">
            ₹{product.price.toLocaleString("en-IN")}
          </div>

          <div className="delivery-box">
            <Truck size={21} />

            <div>
              <strong>Fast Delivery</strong>

              <p>
                Expected delivery: 2–4 business days
              </p>
            </div>
          </div>

          <h3>Specifications</h3>

          <div className="spec-list">
            {product.specs.map((spec) => (
              <div key={spec}>
                <Check size={17} />
                {spec}
              </div>
            ))}
          </div>

          <div className="detail-actions">

            <button
              className="primary-action"
              onClick={handleAddToCart}
            >
              <ShoppingCart size={19} />
              Add to Cart
            </button>

            <button
              className="secondary-action"
              onClick={handleCompare}
            >
              <GitCompare size={19} />
              Compare
            </button>

          </div>

        </div>
      </div>
    </div>
  );
}

export default Product;