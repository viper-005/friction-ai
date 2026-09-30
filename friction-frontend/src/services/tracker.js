const API_URL = "http://localhost:8000";

const CUSTOMER_ID = "DEMO-CUSTOMER-001";

function getSessionId() {
  let sessionId = sessionStorage.getItem("friction_session_id");

  if (!sessionId) {
    sessionId =
      "WEB-" +
      Date.now() +
      "-" +
      Math.random().toString(36).substring(2, 8);

    sessionStorage.setItem("friction_session_id", sessionId);
  }

  return sessionId;
}

export function resetFrictionSession() {
  const sessionId =
    "WEB-" +
    Date.now() +
    "-" +
    Math.random().toString(36).substring(2, 8);

  sessionStorage.setItem("friction_session_id", sessionId);

  return sessionId;
}

export async function trackEvent(eventType, data = {}) {
  const event = {
    customer_id: CUSTOMER_ID,
    session_id: getSessionId(),
    event_type: eventType,
    timestamp: new Date().toISOString(),
    metadata: data,
  };

  console.log("📊 FrictionAI Event:", event);

  try {
    const response = await fetch(`${API_URL}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      console.warn("Backend event tracking failed:", response.status);
      return null;
    }

    const result = await response.json();
    console.log("✅ Event received by FrictionAI:", result);

    return result;
  } catch (error) {
    console.warn("Backend unavailable:", error.message);
    return null;
  }
}

// 🔐 Login / Authentication friction
export async function simulateLoginFriction() {
  resetFrictionSession();

  await trackEvent("product_view", {
    product_id: "DEMO-PRODUCT-LOGIN",
  });

  await trackEvent("add_to_cart", {
    product_id: "DEMO-PRODUCT-LOGIN",
    quantity: 1,
  });

  await trackEvent("checkout_start", {
    amount: 2499,
  });

  await trackEvent("login_failed", {
    attempt: 1,
    reason: "invalid_password",
  });

  await trackEvent("otp_failed", {
    attempt: 1,
    reason: "invalid_otp",
  });

  await trackEvent("login_failed", {
    attempt: 2,
    reason: "authentication_failed",
  });

  await trackEvent("session_exit", {
    reason: "authentication_friction",
  });
}

// 📦 Out-of-stock / Inventory friction
export async function simulateInventoryFriction() {
  resetFrictionSession();

  await trackEvent("product_view", {
    product_id: "DEMO-PRODUCT-STOCK",
  });

  await trackEvent("add_to_cart", {
    product_id: "DEMO-PRODUCT-STOCK",
    quantity: 1,
  });

  await trackEvent("inventory_unavailable", {
    product_id: "DEMO-PRODUCT-STOCK",
    reason: "out_of_stock",
  });

  await trackEvent("session_exit", {
    reason: "inventory_unavailable",
  });
}

// 🎟️ Coupon / Discount friction
export async function simulateCouponFriction() {
  resetFrictionSession();

  await trackEvent("product_view", {
    product_id: "DEMO-PRODUCT-COUPON",
  });

  await trackEvent("add_to_cart", {
    product_id: "DEMO-PRODUCT-COUPON",
    quantity: 1,
  });

  await trackEvent("checkout_start", {
    amount: 2499,
  });

  await trackEvent("coupon_failed", {
    coupon_code: "SAVE20",
    reason: "invalid_or_expired",
  });

  await trackEvent("session_exit", {
    reason: "coupon_friction",
  });
}