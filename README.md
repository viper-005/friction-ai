# FrictionAI 🚀

### Customer Journey Intelligence — Detect → Explain → Recover

FrictionAI is an AI/ML-powered customer journey intelligence platform that detects friction in digital shopping experiences, explains the cause, and recommends recovery actions.

Instead of only showing that a customer abandoned a session, FrictionAI analyzes the customer's journey to identify **where the friction happened, why it happened, how severe it is, and what action can be taken.**

---

## 🎯 Problem

Customer drop-offs can happen because of:

- Payment failures
- Delivery uncertainty
- Product information gaps
- Unexpected price changes
- Post-purchase issues

Traditional analytics can show that a customer abandoned a journey, but they often do not explain the underlying reason or provide an immediate recovery action.

---

## 💡 Our Solution

FrictionAI follows a simple pipeline:

**Detect → Explain → Recover**

### 1. Detect
Customer interactions are captured as structured events from the React frontend.

### 2. Explain
The backend analyzes the customer journey and identifies:

- Risk score
- Friction type
- Root cause
- Evidence
- Confidence
- Recommended action

### 3. Recover
Operations teams can trigger recovery actions directly from the customer investigation dashboard.

---

## 🏗️ Architecture

![FrictionAI Architecture](docs/architecture.png)

### Data Flow

```text
Customer
   ↓
React Frontend
   ↓
Event Tracker
   ↓ HTTP / REST
FastAPI Backend
   ↓
Friction Analyzer
   ↓
Risk + Cause + Recommendation
   ↓
Operations Dashboard
   ↓
Recovery Action