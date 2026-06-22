import sqlite3
from datetime import datetime, timedelta

def days_ago(n):
    """Returns a date string n days before today, in YYYY-MM-DD format."""
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")

# Connect to (or create) the database file
conn = sqlite3.connect("refund_agent.db")
cursor = conn.cursor()

# ── Create customers table ──────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    email       TEXT,
    tier        TEXT,   -- bronze / silver / gold
    total_orders INTEGER,
    is_flagged  INTEGER -- 0 = clean, 1 = fraud flag
)
""")

# ── Create orders table ─────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id     TEXT PRIMARY KEY,
    customer_id  TEXT,
    item_name    TEXT,
    item_type    TEXT,   -- physical / digital
    amount       REAL,
    purchase_date TEXT,  -- YYYY-MM-DD string
    status       TEXT    -- delivered / processing / cancelled
)
""")

# ── 15 customer profiles ────────────────────────────────────────────
customers = [
    ("C001", "Aarav Shah",      "aarav@email.com",   "gold",   32, 0),
    ("C002", "Priya Menon",     "priya@email.com",   "silver", 12, 0),
    ("C003", "Rohan Gupta",     "rohan@email.com",   "bronze",  3, 0),
    ("C004", "Sneha Iyer",      "sneha@email.com",   "gold",   45, 0),
    ("C005", "Vikram Nair",     "vikram@email.com",  "bronze",  1, 1), # fraud flag
    ("C006", "Meera Pillai",    "meera@email.com",   "silver", 18, 0),
    ("C007", "Arjun Desai",     "arjun@email.com",   "bronze",  5, 0),
    ("C008", "Divya Rao",       "divya@email.com",   "gold",   60, 0),
    ("C009", "Karan Singh",     "karan@email.com",   "silver",  9, 0),
    ("C010", "Pooja Sharma",    "pooja@email.com",   "bronze",  2, 1), # fraud flag
    ("C011", "Rahul Joshi",     "rahul@email.com",   "silver", 22, 0),
    ("C012", "Ananya Bose",     "ananya@email.com",  "gold",   38, 0),
    ("C013", "Suresh Patil",    "suresh@email.com",  "bronze",  4, 0),
    ("C014", "Lakshmi Varma",   "lakshmi@email.com", "silver", 15, 0),
    ("C015", "Dev Kapoor",      "dev@email.com",     "gold",   27, 0),
]

cursor.executemany("INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?,?)", customers)

# ── Orders (one per customer, with varied scenarios) ─────────────────
orders = [
    ("O001", "C001", "Running Shoes",    "physical", 2999.0,  days_ago(10), "delivered"),  # gold, recent -> APPROVE
    ("O002", "C002", "Python Course",    "digital",   999.0,  days_ago(5),  "delivered"),  # digital -> DENY
    ("O003", "C003", "Phone Case",       "physical",  299.0,  days_ago(60), "delivered"),  # too old -> DENY
    ("O004", "C004", "Headphones",       "physical", 5999.0,  days_ago(40), "delivered"),  # gold, 40 days -> APPROVE (within 45)
    ("O005", "C005", "T-Shirt",          "physical",  599.0,  days_ago(5),  "delivered"),  # fraud flag -> DENY
    ("O006", "C006", "Yoga Mat",         "physical", 1299.0,  days_ago(15), "delivered"),  # silver, recent -> APPROVE
    ("O007", "C007", "E-Book Bundle",    "digital",   499.0,  days_ago(2),  "delivered"),  # digital -> DENY
    ("O008", "C008", "Smart Watch",      "physical", 8999.0,  days_ago(20), "delivered"),  # gold, recent -> APPROVE
    ("O009", "C009", "Desk Lamp",        "physical",  799.0,  days_ago(35), "delivered"),  # silver, 35 days -> DENY (past 30)
    ("O010", "C010", "Wireless Charger", "physical",  899.0,  days_ago(3),  "delivered"),  # fraud flag -> DENY
    ("O011", "C011", "Backpack",         "physical", 2499.0,  days_ago(8),  "delivered"),  # silver, recent -> APPROVE
    ("O012", "C012", "Air Purifier",     "physical", 12999.0, days_ago(44), "delivered"),  # gold, 44 days -> APPROVE (just inside 45)
    ("O013", "C013", "Notebook Set",     "physical",  399.0,  days_ago(90), "delivered"),  # too old -> DENY
    ("O014", "C014", "Bluetooth Speaker","physical", 3499.0,  days_ago(31), "delivered"),  # silver, 31 days -> DENY (just outside 30)
    ("O015", "C015", "Office Chair",     "physical", 15999.0, days_ago(12), "processing"), # not delivered -> DENY
]

cursor.executemany("INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?,?)", orders)

conn.commit()
conn.close()

print("Database created! 15 customers and 15 orders seeded.")