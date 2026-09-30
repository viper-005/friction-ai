"""Tiny synthetic dataset so the backend runs before Member 4 delivers real data.
Run: python data/generate_sample.py   -> data/events.csv"""
import csv, json, random
from datetime import datetime, timedelta
random.seed(7)
rows = []
base = datetime(2026, 9, 28, 10, 0)

def add(cid, t, ev, **meta):
    rows.append([cid, t.isoformat(), ev, json.dumps(meta) if meta else ""])
    return t + timedelta(seconds=random.randint(15, 60))

def payment_fail(cid, t0):
    t = add(cid, t0, "product_view", product_id="P1")
    t = add(cid, t, "add_to_cart", product_id="P1", cart_value=2499)
    t = add(cid, t, "checkout_start")
    for _ in range(3):
        t = add(cid, t, "payment_failed", method="UPI", reason="bank_timeout")
    add(cid, t, "exit")

def delivery(cid, t0):
    t = add(cid, t0, "add_to_cart", product_id="P2", cart_value=5999)
    t = add(cid, t, "checkout_start")
    t = add(cid, t, "delivery_check", pincode="560001", dwell_seconds=45)
    t = add(cid, t, "delivery_check", pincode="560001", dwell_seconds=38)
    add(cid, t, "exit")

def price(cid, t0):
    t = add(cid, t0, "add_to_cart", product_id="P3", cart_value=899)
    t = add(cid, t, "checkout_start")
    t = add(cid, t, "shipping_shown", shipping_cost=149, cart_value=899)
    add(cid, t, "exit")

def info(cid, t0):
    t = t0
    for p in ["P4", "P5", "P6", "P4", "P5"]:
        t = add(cid, t, "compare_products" if random.random() < .5 else "product_view", product_id=p)
    add(cid, t, "exit")

def post(cid, t0):
    t = add(cid, t0, "add_to_cart", product_id="P7", cart_value=1999)
    t = add(cid, t, "order_placed", order_id="O1")
    t += timedelta(days=3)
    add(cid, t, "support_ticket", topic="order delayed, no tracking update")

def happy(cid, t0):
    t = add(cid, t0, "product_view", product_id="P8")
    t = add(cid, t, "add_to_cart", product_id="P8", cart_value=1200)
    t = add(cid, t, "checkout_start")
    t = add(cid, t, "payment_attempt", method="card")
    add(cid, t, "order_placed", order_id="O2")

scen = [payment_fail, delivery, price, info, post, happy]
for i in range(60):
    fn = scen[i % len(scen)] if i < 12 else random.choices(scen, weights=[2, 2, 2, 2, 1, 6])[0]
    fn(f"cust_{i:03d}", base + timedelta(hours=random.randint(0, 40), minutes=random.randint(0, 59)))
rows.sort(key=lambda r: r[1])
with open("data/events.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["customer_id", "timestamp", "event_type", "metadata"]); w.writerows(rows)
print(len(rows), "events written")
