import sqlite3
from datetime import datetime
import random
from datetime import timedelta

DB_PATH = "refund_agent.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


# ── TOOL 1: Look up customer ──────────────────────────────────────
def lookup_customer(customer_id: str) -> dict:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM customers WHERE UPPER(id) = UPPER(?)", (customer_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return {"found": False, "error": f"No customer with id {customer_id}"}

    return {
        "found": True,
        "id": row["id"],
        "name": row["name"],
        "tier": row["tier"],
        "total_orders": row["total_orders"],
        "is_flagged": bool(row["is_flagged"]),
    }


# ── TOOL 2: Check order status ────────────────────────────────────
def check_order_status(order_id: str) -> dict:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM orders WHERE UPPER(order_id) = UPPER(?)", (order_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return {"found": False, "error": f"No order with id {order_id}"}

    purchase_date = datetime.strptime(row["purchase_date"], "%Y-%m-%d")
    days_since_purchase = (datetime.now() - purchase_date).days

    return {
        "found": True,
        "order_id": row["order_id"],
        "customer_id": row["customer_id"],
        "item_name": row["item_name"],
        "item_type": row["item_type"],
        "amount": row["amount"],
        "status": row["status"],
        "days_since_purchase": days_since_purchase,
    }


# ── TOOL 3: Validate against policy rules ─────────────────────────
def validate_policy(customer_info: dict, order_info: dict) -> dict:
    """
    Applies the rules from policy.md directly in code.
    Returns approved/denied + the reason.
    """
    # Rule: fraud flag overrides everything
    if customer_info.get("is_flagged"):
        return {"approved": False, "reason": "Customer account is flagged for fraud."}

    # Rule: order must be delivered
    if order_info.get("status") != "delivered":
        return {"approved": False, "reason": f"Order status is '{order_info.get('status')}', not 'delivered'."}

    # Rule: digital items are never refundable
    if order_info.get("item_type") == "digital":
        return {"approved": False, "reason": "Digital items are final sale and not eligible for refund."}

    # Rule: refund window depends on tier
    window_days = 45 if customer_info.get("tier") == "gold" else 30
    days_since = order_info.get("days_since_purchase", 9999)

    if days_since > window_days:
        return {
            "approved": False,
            "reason": f"Order was placed {days_since} days ago, which exceeds the {window_days}-day refund window."
        }

    return {
        "approved": True,
        "reason": f"All policy conditions met. Within {window_days}-day window, item is physical, order delivered, no fraud flag."
    }






# ── TOOL 5: List a customer's recent orders ───────────────────────
def list_orders_for_customer(customer_id: str) -> dict:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM orders WHERE UPPER(customer_id) = UPPER(?)", (customer_id,)
    ).fetchall()
    conn.close()

    if not rows:
        return {"found": False, "error": f"No orders found for customer {customer_id}"}

    orders = []
    for row in rows:
        purchase_date = datetime.strptime(row["purchase_date"], "%Y-%m-%d")
        days_since = (datetime.now() - purchase_date).days
        orders.append({
            "order_id": row["order_id"],
            "item_name": row["item_name"],
            "amount": row["amount"],
            "days_since_purchase": days_since,
            "status": row["status"],
        })

    return {"found": True, "orders": orders}



# Tracks which order_ids have had a pickup scheduled (very simple, in-memory)
pickup_scheduled_orders = set()


def schedule_pickup(order_id: str) -> dict:
    pickup_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    tracking_id = f"PU-{random.randint(10000, 99999)}"

    pickup_scheduled_orders.add(order_id)  # mark it as scheduled

    return {
        "scheduled": True,
        "order_id": order_id,
        "pickup_date": pickup_date,
        "tracking_id": tracking_id,
        "message": f"Pickup scheduled for {pickup_date}. Tracking ID: {tracking_id}. Refund will be processed after the item is received back."
    }


def process_refund(order_id: str, amount: float) -> dict:
    # Hard guard: refuse to process a refund if pickup wasn't scheduled first.
    if order_id not in pickup_scheduled_orders:
        return {
            "success": False,
            "error": f"Cannot process refund for {order_id} — pickup has not been scheduled yet. Call tool_schedule_pickup first."
        }

    return {
        "success": True,
        "status": "pending_pickup",
        "order_id": order_id,
        "refunded_amount": amount,
        "message": f"Refund of ₹{amount} for order {order_id} is approved and will be processed once the returned item is received."
    }







