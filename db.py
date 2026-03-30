"""
db.py — AlloyDB (PostgreSQL) database layer

- Connection pooling via psycopg2.pool
- Auto-creates and seeds the products table on first run
- Executes SELECT queries and returns JSON-safe results
- Exposes schema metadata for the AI prompt
"""

import logging
from decimal import Decimal
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, TABLE_NAME

log = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None


# ── Pool management ────────────────────────────────────────────────────────

def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1, maxconn=10,
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            connect_timeout=10,
        )
        log.info("AlloyDB connection pool created")
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)


# ── Seed data (20 products across 5 categories) ────────────────────────────

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


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id          SERIAL PRIMARY KEY,
    name        TEXT           NOT NULL,
    category    TEXT           NOT NULL,
    price       NUMERIC(10,2)  NOT NULL,
    stock       INTEGER        NOT NULL DEFAULT 0,
    rating      NUMERIC(3,1),
    description TEXT,
    created_at  TIMESTAMPTZ    DEFAULT NOW()
);
"""

CREATE_INDEXES_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_category ON {TABLE_NAME}(category);
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_price    ON {TABLE_NAME}(price);
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_rating   ON {TABLE_NAME}(rating);
"""


def init_db() -> bool:
    """
    Create table + indexes and seed data if table is empty.
    Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Try enabling pgvector (available on AlloyDB)
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
            except Exception:
                conn.rollback()
                log.info("pgvector not available (OK for local dev)")

            cur.execute(CREATE_TABLE_SQL)
            for stmt in CREATE_INDEXES_SQL.strip().split("\n"):
                if stmt.strip():
                    cur.execute(stmt)

            cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};")
            count = cur.fetchone()[0]
            if count == 0:
                cur.executemany(
                    f"""INSERT INTO {TABLE_NAME}
                        (name, category, price, stock, rating, description)
                        VALUES (%s,%s,%s,%s,%s,%s)""",
                    SEED_PRODUCTS,
                )
                log.info(f"Seeded {len(SEED_PRODUCTS)} products into {TABLE_NAME}")
            else:
                log.info(f"Table {TABLE_NAME} already has {count} rows")

        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        log.error(f"init_db failed: {exc}")
        return False
    finally:
        if conn:
            put_conn(conn)


# ── Query execution ────────────────────────────────────────────────────────

def _serialize(val):
    """Make a value JSON-safe."""
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val


def execute_query(sql: str, params=None) -> dict:
    """
    Execute a SQL SELECT and return:
      { columns, rows, count, error }
    All values are JSON-serialisable.
    """
    conn = None
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            raw = cur.fetchall()
            rows = [{k: _serialize(v) for k, v in row.items()} for row in raw]
            return {
                "columns": list(rows[0].keys()) if rows else [],
                "rows":    rows,
                "count":   len(rows),
                "error":   None,
            }
    except Exception as exc:
        if conn:
            conn.rollback()
        log.error(f"execute_query error: {exc}\nSQL: {sql}")
        return {"columns": [], "rows": [], "count": 0, "error": str(exc)}
    finally:
        if conn:
            put_conn(conn)


def get_table_stats() -> dict:
    """Return summary stats for the dashboard."""
    result = execute_query(f"""
        SELECT
            COUNT(*)                          AS total_products,
            COUNT(DISTINCT category)          AS total_categories,
            ROUND(AVG(price)::numeric, 2)     AS avg_price,
            MIN(price)                        AS min_price,
            MAX(price)                        AS max_price,
            ROUND(AVG(rating)::numeric, 2)    AS avg_rating,
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
  price       NUMERIC(10,2)  – price in USD (e.g. 49.99)
  stock       INTEGER        – units currently in stock
  rating      NUMERIC(3,1)   – customer rating from 0.0 to 5.0
  description TEXT           – short product description
  created_at  TIMESTAMPTZ    – row creation timestamp

Sample values:
  categories : Electronics, Kitchen, Sports, Furniture, Home
  price range: $19.99 – $329.00
  stock range: 12 – 150 units
  rating range: 4.2 – 4.9

Total rows: ~20 products"""