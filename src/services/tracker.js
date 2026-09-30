const API_URL = "http://localhost:8000";

export async function trackEvent(eventType, data = {}) {
  const event = {
    customer_id: "DEMO-CUSTOMER-001",
    event_type: eventType,
    timestamp: new Date().toISOString(),
    ...data
  };

  console.log("📊 Customer Event:", event);

  try {
    const response = await fetch(`${API_URL}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(event)
    });

    if (!response.ok) {
      console.warn("Backend event tracking failed.");
      return null;
    }

    return await response.json();
  } catch (error) {
    console.warn("Backend unavailable:", error.message);
    return null;
  }
}