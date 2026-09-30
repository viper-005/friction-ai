import { useState } from "react";
import { Search, ShieldCheck, Zap, Brain } from "lucide-react";
import ProductCard from "../components/ProductCard";
import { products } from "../data/products";
import { trackEvent } from "../services/tracker";

function Home({ addToCart }) {
  const [search, setSearch] = useState("");

  const filteredProducts = products.filter((product) =>
    `${product.name} ${product.category}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const handleProductView = (product) => {
    trackEvent("product_view", {
      product_id: product.id,
      product_name: product.name,
      category: product.category
    });
  };

  return (
    <div className="home-page">

      <section className="hero">
        <div className="hero-content">
          <div className="hero-badge">
            <Brain size={16} />
            AI-Powered Shopping Experience
          </div>

          <h1>
            Shop smarter.
            <br />
            <span>Experience less friction.</span>
          </h1>

          <p>
            Discover products with a seamless shopping
            experience powered by intelligent journey analysis.
          </p>

          <div className="hero-features">
            <div>
              <ShieldCheck size={18} />
              Secure Shopping
            </div>

            <div>
              <Zap size={18} />
              Fast Checkout
            </div>

            <div>
              <Brain size={18} />
              AI Assistance
            </div>
          </div>
        </div>
      </section>

      <section className="products-section">

        <div className="section-header">
          <div>
            <span className="section-label">EXPLORE</span>
            <h2>Featured Products</h2>
          </div>

          <div className="search-box">
            <Search size={19} />

            <input
              type="text"
              placeholder="Search products..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);

                if (e.target.value) {
                  trackEvent("product_search", {
                    query: e.target.value
                  });
                }
              }}
            />
          </div>
        </div>

        <div className="product-grid">
          {filteredProducts.map((product) => (
            <div
              key={product.id}
              onMouseEnter={() => handleProductView(product)}
            >
              <ProductCard
                product={product}
                onAddToCart={addToCart}
              />
            </div>
          ))}
        </div>

        {filteredProducts.length === 0 && (
          <div className="empty-search">
            <h3>No products found</h3>
            <p>Try searching for something else.</p>
          </div>
        )}
      </section>
    </div>
  );
}

export default Home;