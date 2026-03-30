"""
sqlite_db.py — SQLite database layer (fallback for demo purposes)

Same interface as db.py but uses SQLite instead of PostgreSQL.
This allows the application to run without external database setup.
"""

import logging
import sqlite3
from decimal import Decimal
from contextlib import contextmanager
from config import TABLE_NAME

log = logging.getLogger(__name__)

# ── Seed data (same as in db.py) ────────────────────────────────────────────

SEED_PRODUCTS = [
    # (name, category, price, stock, rating, description)
    ("Wireless Noise-Cancelling Headphones", "Electronics", 149.99, 35, 4.7,
     "Over-ear ANC headphones with 30-hour battery and premium sound."),
    ("Ergonomic Office Chair",               "Furniture",   329.00, 12, 4.5,
     "Lumbar-support mesh chair for all-day comfort and posture."),
    ("Stainless Steel Water Bottle",         "Kitchen",      24.95, 120, 4.8,
     "32oz double-walled insulated bottle, cold 24h or hot 12h."),
    ("Mechanical Keyboard TKL",              "Electronics",  89.99,  60, 4.6,
     "Cherry MX Brown switches, RGB backlight, compact tenkeyless."),
    ("Yoga Mat Premium",                     "Sports",       45.00,  80, 4.4,
     "6mm non-slip TPE foam with alignment lines, eco-friendly."),
    ("Air Purifier HEPA 500sqft",            "Home",        199.00,  25, 4.3,
     "Covers 500 sq ft, removes 99.97% of particles ≥0.3 microns."),
    ("Portable Bluetooth Speaker",           "Electronics",  59.99,  45, 4.5,
     "IPX7 waterproof, 360-degree sound, 12-hour playback."),
    ("Cast Iron Skillet 12in",               "Kitchen",      39.95,  70, 4.9,
     "Pre-seasoned, works on all cooktops including induction."),
    ("Standing Desk Converter",              "Furniture",   249.00,  18, 4.2,
     "Sit-stand riser with gas-spring lift, smooth height adjustment."),
    ("Running Shoes Pro",                    "Sports",      119.99,  55, 4.6,
     "Breathable mesh upper, responsive foam midsole for long runs."),
    ("Smart LED Desk Lamp",                  "Electronics",  49.99,  90, 4.5,
     "Touch-control with 5 colour temps and USB-C charging port."),
    ("French Press Coffee Maker",            "Kitchen",      34.99,  65, 4.7,
     "8-cup borosilicate glass, stainless double-screen filter."),
    ("Foam Roller Deep Tissue",              "Sports",       29.99, 100, 4.3,
     "High-density EVA foam, 36-inch length for full-back coverage."),
    ("Weighted Blanket 15lb",                "Home",         79.00,  40, 4.6,
     "Glass-bead fill in 48x72in premium cotton shell."),
    ("White Noise Sleep Machine",            "Home",         44.95,  55, 4.8,
     "30 soothing sounds, auto-off timer, compact bedside design."),
    ("4K Webcam Pro",                        "Electronics",  99.99,  30, 4.4,
     "4K autofocus, built-in ring light and noise-cancelling mic."),
    ("Bamboo Cutting Board Set",             "Kitchen",      32.00,  85, 4.6,
     "3-piece set with juice grooves, naturally antimicrobial."),
    ("Resistance Bands Set",                 "Sports",       19.99, 150, 4.5,
     "5 resistance levels, latex-free, includes carry bag."),
    ("Electric Kettle 1.7L",                 "Kitchen",      44.99,  60, 4.7,
     "1500W rapid boil, 6 temperature presets, keep-warm mode."),
    ("Monitor Light Bar",                    "Electronics",  35.99,  75, 4.5,
     "Auto-dimming sensor, no screen glare, USB-C powered."),
]

DB_FILE = "alloydb_demo.db"

# ── Connection management ─────────────────────────────────────────────────────

@contextmanager
def get_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    try:
        yield conn
    finally:
        conn.close()

# ── Database initialization ───────────────────────────────────────────────────

def init_db() -> bool:
    """Create table and seed data if needed."""
    try:
        with get_conn() as conn:
            # Create table
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL,
                    stock INTEGER NOT NULL DEFAULT 0,
                    rating REAL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if data exists
            cursor = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Seed data
                conn.executemany(
                    f"INSERT INTO {TABLE_NAME} (name, category, price, stock, rating, description) VALUES (?, ?, ?, ?, ?, ?)",
                    SEED_PRODUCTS
                )
                log.info(f"Seeded {len(SEED_PRODUCTS)} products into {TABLE_NAME}")
            else:
                log.info(f"Table {TABLE_NAME} already has {count} rows")
            
            conn.commit()
        return True
        
    except Exception as exc:
        log.error(f"init_db failed: {exc}")
        return False

# ── Query execution ────────────────────────────────────────────────────────

def _serialize(val):
    """Make a value JSON-safe."""
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val

def execute_query(sql: str, params=None) -> dict:
    """Execute a SQL SELECT and return JSON-safe results."""
    try:
        with get_conn() as conn:
            cursor = conn.execute(sql, params or ())
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            data = []
            for row in rows:
                data.append({k: _serialize(v) for k, v in dict(row).items()})
            
            return {
                "columns": list(data[0].keys()) if data else [],
                "rows": data,
                "count": len(data),
                "error": None,
            }
    except Exception as exc:
        log.error(f"execute_query error: {exc}\nSQL: {sql}")
        return {"columns": [], "rows": [], "count": 0, "error": str(exc)}

# ── Utility functions ─────────────────────────────────────────────────────

def get_table_stats() -> dict:
    """Return summary stats for the dashboard."""
    result = execute_query(f"""
        SELECT
            COUNT(*)                          AS total_products,
            COUNT(DISTINCT category)          AS total_categories,
            ROUND(AVG(price), 2)              AS avg_price,
            MIN(price)                        AS min_price,
            MAX(price)                        AS max_price,
            ROUND(AVG(rating), 2)             AS avg_rating,
            MAX(rating)                       AS max_rating,
            SUM(stock)                        AS total_stock
        FROM {TABLE_NAME};
    """)
    return result["rows"][0] if result["rows"] else {}

def get_all_rows() -> dict:
    return execute_query(
        f"SELECT id, name, category, price, stock, rating, description "
        f"FROM {TABLE_NAME} ORDER BY id;"
    )

def get_schema_text() -> str:
    return f"""Table name: {TABLE_NAME}

Columns:
  id          INTEGER        – auto-increment primary key
  name        TEXT           – product name (e.g. "Wireless Headphones")
  category    TEXT           – one of: Electronics, Kitchen, Sports, Furniture, Home
  price       REAL           – price in USD (e.g. 49.99)
  stock       INTEGER        – units currently in stock
  rating      REAL           – customer rating from 0.0 to 5.0
  description TEXT           – short product description
  created_at  TIMESTAMP      – row creation timestamp

Sample values:
  categories : Electronics, Kitchen, Sports, Furniture, Home
  price range: $19.99 – $329.00
  stock range: 12 – 150 units
  rating range: 4.2 – 4.9

Total rows: ~20 products"""
