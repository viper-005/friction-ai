import { useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
} from "react-router-dom";

import Navbar from "./components/Navbar";

import Home from "./pages/Home";
import Product from "./pages/Product";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";

import "./index.css";
import Dashboard from "./pages/Dashboard";
import CustomerDetails from "./pages/CustomerDetails";

function App() {
  const [cart, setCart] = useState([]);

  const addToCart = (product) => {
    setCart((currentCart) => {
      const existing = currentCart.find(
        (item) => item.id === product.id
      );

      if (existing) {
        return currentCart.map((item) =>
          item.id === product.id
            ? {
                ...item,
                quantity: item.quantity + 1,
              }
            : item
        );
      }

      return [
        ...currentCart,
        {
          ...product,
          quantity: 1,
        },
      ];
    });
  };

  const updateQuantity = (id, quantity) => {
    if (quantity <= 0) {
      removeFromCart(id);
      return;
    }

    setCart((currentCart) =>
      currentCart.map((item) =>
        item.id === id
          ? { ...item, quantity }
          : item
      )
    );
  };

  const removeFromCart = (id) => {
    setCart((currentCart) =>
      currentCart.filter((item) => item.id !== id)
    );
  };

  const clearCart = () => {
    setCart([]);
  };

  const cartCount = cart.reduce(
    (total, item) => total + item.quantity,
    0
  );

  return (
    <BrowserRouter>
      <Navbar cartCount={cartCount} />

      <main>
       <Routes>

  <Route
    path="/"
    element={<Home addToCart={addToCart} />}
  />

  <Route
    path="/product/:id"
    element={<Product addToCart={addToCart} />}
  />

  <Route
    path="/cart"
    element={
      <Cart
        cart={cart}
        updateQuantity={updateQuantity}
        removeFromCart={removeFromCart}
      />
    }
  />

  <Route
    path="/checkout"
    element={
      <Checkout
        cart={cart}
        clearCart={clearCart}
      />
    }
  />

  <Route
    path="/dashboard"
    element={<Dashboard />}
  />

  <Route
    path="/customers"
    element={<Dashboard />}
  />

  <Route
    path="/customer/:id"
    element={<CustomerDetails />}
  />

</Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;