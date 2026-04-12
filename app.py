"""
app.py — Flask REST API + UI server

Routes:
  GET  /                → main UI
  GET  /api/health      → liveness + DB/AI status check
  GET  /api/stats       → dashboard statistics
  GET  /api/schema      → table schema text
  GET  /api/browse      → all rows (for Browse tab)
  POST /api/query       → full NL→SQL→execute→summarise pipeline
  POST /api/execute     → run a raw SQL string (validated)
  POST /api/chat        → AI chatbot (multi-turn)
  POST /api/ask         → simple question-answering endpoint
  POST /api/auth/register → user registration
  POST /api/auth/login    → user login
  GET  /api/auth/me     → get current user profile
"""

import logging
import sys
import time
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from config import SECRET_KEY, DEBUG, ANTHROPIC_API_KEY

# Import new backend modules
from cache import cache_query, cache_stats, get_cache_stats, clear_all_caches
from middleware import setup_middleware, rate_limit, get_metrics
from health import init_health_monitor, get_health_monitor, check_system_resources
from auth import (
    register_user, authenticate_user, get_user_by_id, login_required,
    validate_email, validate_password, AuthError, decode_token, get_auth_token
)
from google_auth import verify_google_token, get_or_create_user
from credits import (
    check_anonymous_quota, record_anonymous_usage, get_user_credits,
    add_credits, deduct_credits, initialize_user_credits, process_payment,
    get_credit_packages, record_query, get_query_history, get_user_stats,
    FREE_CREDITS_ON_SIGNUP, FREE_QUERIES_ANONYMOUS
)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# Try to import PostgreSQL db, fallback to SQLite if connection fails
try:
    import psycopg2
    import psycopg2.pool
    from db import init_db, execute_query, get_table_stats, get_all_rows, get_schema_text, TABLE_NAME
    
    # Test if PostgreSQL is actually available
    try:
        test_conn = init_db()
        if test_conn:
            DB_TYPE = "postgresql"
            log.info("Using PostgreSQL database")
        else:
            raise Exception("PostgreSQL init failed")
    except Exception as e:
        log.warning(f"PostgreSQL not available: {e}")
        raise ImportError("Fallback to SQLite")
        
except ImportError:
    from sqlite_db import init_db, execute_query, get_table_stats, get_all_rows, get_schema_text, TABLE_NAME
    DB_TYPE = "sqlite"
    log.info("Using SQLite database (PostgreSQL not available)")

# Import AI layer - use demo if no API key
if ANTHROPIC_API_KEY:
    from ai import nl_to_sql, summarise, chat, validate_sql
    AI_TYPE = "claude"
    log.info("Using Claude AI")
else:
    from demo_ai import nl_to_sql, summarise, chat, validate_sql
    AI_TYPE = "demo"
    log.info("Using demo AI (no API key configured)")

# Wrap AI functions with caching
nl_to_sql = cache_query(ttl=60, key_prefix="nl_to_sql")(nl_to_sql)
summarise = cache_query(ttl=60, key_prefix="summarise")(summarise)

# ── App setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# Setup middleware (rate limiting, logging, security headers)
setup_middleware(app)

_db_ok  = False
_ai_ok  = False


@app.before_request
def startup():
    """One-time init on first request."""
    global _db_ok, _ai_ok
    if not getattr(app, "_started", False):
        app._started = True
        app._start_time = time.time()

        _db_ok = init_db()
        _ai_ok = True  # AI is always ready now (either Claude or demo)

        # Initialize health monitor
        init_health_monitor(DB_TYPE)

        if _db_ok:
            log.info(f"Database ready ({DB_TYPE})")
        else:
            log.warning("Database unavailable")

        if AI_TYPE == "claude":
            log.info("Claude AI ready")
        else:
            log.info("Demo AI ready")
        
        log.info("Backend upgrades loaded: caching, rate limiting, health monitoring")


# ── Helper ─────────────────────────────────────────────────────────────────

def err(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ── UI ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", ai_enabled=_ai_ok, db_enabled=_db_ok)


# ── API ────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({
        "status":     "ok",
        "db_ready":   _db_ok,
        "db_type":    DB_TYPE,
        "ai_ready":   _ai_ok,
        "ai_type":    AI_TYPE,
        "table":      TABLE_NAME,
    })


@app.route("/api/stats")
@cache_stats(ttl=60)
def stats():
    data = get_table_stats()
    return jsonify(data)


@app.route("/api/schema")
def schema():
    return jsonify({"schema": get_schema_text()})


@app.route("/api/browse")
def browse():
    result = get_all_rows()
    return jsonify(result)


@app.route("/api/query", methods=["POST"])
@rate_limit("query")
def query():
    """
    Full pipeline: natural language → SQL → execute → AI summary.
    Body: { "question": "show me electronics under $100" }
    """
    body     = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()

    if not question:
        return err("Question is required.")

    # Step 1 – NL → SQL
    nl_result = nl_to_sql(question)
    if nl_result["error"]:
        return jsonify({"error": nl_result["error"], "step": "nl_to_sql"}), 422

    sql = nl_result["sql"]

    # Step 2 – Execute on database
    if not _db_ok:
        return jsonify({
            "sql":     sql,
            "columns": [],
            "rows":    [],
            "count":   0,
            "summary": "Database is not connected. The SQL was generated but could not be executed.",
            "error":   "Database unavailable",
        })

    db_result = execute_query(sql)

    # Step 3 – Summarise
    summary = summarise(question, db_result["rows"], db_result["count"])

    return jsonify({
        "sql":     sql,
        "columns": db_result["columns"],
        "rows":    db_result["rows"],
        "count":   db_result["count"],
        "summary": summary,
        "error":   db_result.get("error"),
    })


@app.route("/api/execute", methods=["POST"])
@rate_limit("execute")
def execute():
    """
    Execute a raw SQL string (must be SELECT).
    Body: { "sql": "SELECT ..." }
    """
    body = request.get_json(silent=True) or {}
    sql  = (body.get("sql") or "").strip()

    if not sql:
        return err("SQL is required.")

    check = validate_sql(sql)
    if not check["ok"]:
        return err(f"SQL rejected: {check['reason']}", 422)

    result = execute_query(sql)
    return jsonify(result)


@app.route("/api/chat", methods=["POST"])
def chatbot():
    """
    Multi-turn AI chatbot.
    Body: { "messages": [{"role":"user","content":"..."}, ...] }
    """
    body     = request.get_json(silent=True) or {}
    messages = body.get("messages") or []

    if not messages:
        return err("messages array is required.")

    if not _ai_ok:
        return jsonify({"reply": "AI is not configured. Please add your ANTHROPIC_API_KEY to the .env file."})

    reply = chat(messages)
    return jsonify({"reply": reply})


@app.route("/api/ask", methods=["POST"])
@rate_limit("ask")
def ask():
    """
    Simple question-answering endpoint.
    Takes a natural language question and returns a direct answer.
    Body: { "question": "What is the most expensive product?" }
    Returns: { "answer": "The most expensive product is...", "data": [...] }
    """
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    
    if not question:
        return err("Question is required.")
    
    try:
        # Step 1: Convert question to SQL
        nl_result = nl_to_sql(question)
        if nl_result["error"]:
            return jsonify({
                "answer": f"I couldn't understand your question: {nl_result['error']}",
                "data": [],
                "sql": None
            }), 422
        
        sql = nl_result["sql"]
        
        # Step 2: Execute query (if database is available)
        if not _db_ok:
            return jsonify({
                "answer": f"I generated this SQL but can't execute it without a database: {sql}",
                "data": [],
                "sql": sql
            })
        
        db_result = execute_query(sql)
        
        # Step 3: Generate natural language answer
        if db_result["error"]:
            return jsonify({
                "answer": f"Database error: {db_result['error']}",
                "data": [],
                "sql": sql
            })
        
        # Generate answer based on results
        if db_result["count"] == 0:
            answer = "No products match your query."
        else:
            # Use AI to generate a natural language answer
            answer = summarise(question, db_result["rows"], db_result["count"])
        
        return jsonify({
            "answer": answer,
            "data": db_result["rows"],
            "sql": sql,
            "count": db_result["count"]
        })
        
    except Exception as exc:
        log.error(f"ask endpoint error: {exc}")
        return err(f"An error occurred: {str(exc)}", 500)


# ── Monitoring & Admin Endpoints ────────────────────────────────────────────

@app.route("/api/health/detailed")
def health_detailed():
    """Detailed health check with database diagnostics."""
    health_monitor = get_health_monitor()
    if not health_monitor:
        return jsonify({"error": "Health monitor not initialized"}), 503
    
    # Run health check
    db_health = health_monitor.check_database_health(
        lambda: execute_query("SELECT 1")
    )
    
    return jsonify({
        "system": {
            "uptime_seconds": int(time.time() - getattr(app, '_start_time', time.time())),
            "python_version": sys.version.split()[0],
            "memory_usage": check_system_resources()
        },
        "database": db_health,
        "services": {
            "database": _db_ok,
            "ai": _ai_ok,
            "db_type": DB_TYPE,
            "ai_type": AI_TYPE
        }
    })


@app.route("/api/metrics")
def metrics():
    """API usage metrics and statistics."""
    return jsonify(get_metrics())


@app.route("/api/cache/stats")
def cache_stats_endpoint():
    """Cache performance statistics."""
    return jsonify(get_cache_stats())


@app.route("/api/cache/clear", methods=["POST"])
def cache_clear():
    """Clear all caches."""
    clear_all_caches()
    return jsonify({"status": "ok", "message": "All caches cleared"})


@app.route("/api/status")
def system_status():
    """Complete system status overview."""
    health_monitor = get_health_monitor()
    
    return jsonify({
        "timestamp": time.time(),
        "status": "operational" if (_db_ok and _ai_ok) else "degraded",
        "uptime_seconds": int(time.time() - getattr(app, '_start_time', time.time())),
        "services": {
            "database": {"ready": _db_ok, "type": DB_TYPE},
            "ai": {"ready": _ai_ok, "type": AI_TYPE}
        },
        "caching": get_cache_stats(),
        "api_metrics": get_metrics(),
        "health": health_monitor.get_health_summary() if health_monitor else None
    })


# ── Authentication Endpoints ────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
@rate_limit("default")
def register():
    """
    Register a new user with email and password.
    Body: { "email": "user@example.com", "password": "SecurePass123!", "name": "John" }
    Returns: { "user": { "id": 1, "email": "...", "name": "..." }, "token": "..." }
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    name = (body.get("name") or "").strip()
    
    if not email or not password:
        return err("Email and password are required.")
    
    if not _db_ok:
        return err("Database unavailable", 503)
    
    try:
        if DB_TYPE == "postgresql":
            conn = get_conn()
            try:
                user = register_user(conn, email, password, name)
                conn.commit()
            finally:
                put_conn(conn)
        else:
            with get_conn() as conn:
                user = register_user(conn, email, password, name)
                conn.commit()
        
        # Generate token for immediate login
        from auth import generate_token
        token = generate_token(user["id"], user["email"])
        
        return jsonify({
            "status": "success",
            "message": "User registered successfully",
            "user": user,
            "token": token
        }), 201
        
    except AuthError as e:
        return err(str(e), 400)
    except Exception as exc:
        log.error(f"Registration error: {exc}")
        return err("Registration failed", 500)


@app.route("/api/auth/login", methods=["POST"])
@rate_limit("default")
def login():
    """
    Authenticate user with email and password.
    Body: { "email": "user@example.com", "password": "SecurePass123!" }
    Returns: { "user": { "id": 1, "email": "...", "name": "..." }, "token": "..." }
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    
    if not email or not password:
        return err("Email and password are required.")
    
    if not _db_ok:
        return err("Database unavailable", 503)
    
    try:
        if DB_TYPE == "postgresql":
            conn = get_conn()
            try:
                result = authenticate_user(conn, email, password)
                if result:
                    # Update last login
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE users SET last_login_at = NOW() WHERE id = %s",
                        (result["id"],)
                    )
                conn.commit()
            finally:
                put_conn(conn)
        else:
            with get_conn() as conn:
                result = authenticate_user(conn, email, password)
                if result:
                    # Update last login
                    conn.execute(
                        "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (result["id"],)
                    )
                conn.commit()
        
        if not result:
            return err("Invalid email or password", 401)
        
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": {
                "id": result["id"],
                "email": result["email"],
                "name": result["name"]
            },
            "token": result["token"]
        })
        
    except Exception as exc:
        log.error(f"Login error: {exc}")
        return err("Login failed", 500)


@app.route("/api/auth/me", methods=["GET"])
@login_required
def get_current_user():
    """
    Get current authenticated user profile.
    Headers: Authorization: Bearer <token>
    Returns: { "user": { "id": 1, "email": "...", "name": "..." }, "credits": 200 }
    """
    user_id = g.current_user.get("user_id")
    
    if not _db_ok:
        return err("Database unavailable", 503)
    
    try:
        if DB_TYPE == "postgresql":
            conn = get_conn()
            try:
                user = get_user_by_id(conn, user_id)
                credits = get_user_credits(user_id)
            finally:
                put_conn(conn)
        else:
            with get_conn() as conn:
                user = get_user_by_id(conn, user_id)
                credits = get_user_credits(user_id)
        
        if not user:
            return err("User not found", 404)
        
        return jsonify({
            "status": "success",
            "user": user,
            "credits": credits
        })
        
    except Exception as exc:
        log.error(f"Get user error: {exc}")
        return err("Failed to get user profile", 500)


@app.route("/api/auth/google", methods=["POST"])
@rate_limit("default")
def google_auth():
    """
    Google Sign-In authentication.
    Body: { "id_token": "..." }
    Returns: { "user": {...}, "token": "...", "credits": 200 }
    """
    body = request.get_json(silent=True) or {}
    id_token = body.get("id_token")
    
    if not id_token:
        return err("Google ID token is required")
    
    if not _db_ok:
        return err("Database unavailable", 503)
    
    try:
        # Verify Google token
        google_user = verify_google_token(id_token)
        if not google_user:
            return err("Invalid Google token", 401)
        
        # Get or create user
        if DB_TYPE == "postgresql":
            conn = get_conn()
            try:
                user = get_or_create_user(conn, google_user)
                conn.commit()
            finally:
                put_conn(conn)
        else:
            with get_conn() as conn:
                user = get_or_create_user(conn, google_user)
                conn.commit()
        
        # Initialize credits for new users
        if user.get("is_new"):
            credits = initialize_user_credits(user["id"])
        else:
            credits = get_user_credits(user["id"])
        
        # Generate token
        from auth import generate_token
        token = generate_token(user["id"], user["email"])
        
        return jsonify({
            "status": "success",
            "message": "Google sign-in successful",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "picture": user.get("picture", "")
            },
            "token": token,
            "credits": credits,
            "is_new": user.get("is_new", False)
        })
        
    except Exception as exc:
        log.error(f"Google auth error: {exc}")
        return err("Authentication failed", 500)


@app.route("/api/credits/packages", methods=["GET"])
def credit_packages():
    """Get available credit packages."""
    return jsonify({
        "packages": get_credit_packages()
    })


@app.route("/api/payment/process", methods=["POST"])
@login_required
def process_credit_payment():
    """
    Process payment for credits.
    Body: { "package_id": "...", "credits": 500, "amount": 199, "method": "upi|card", "details": {...} }
    """
    user_id = g.current_user.get("user_id")
    body = request.get_json(silent=True) or {}
    
    package_id = body.get("package_id")
    credits = body.get("credits")
    amount = body.get("amount")
    method = body.get("method")
    details = body.get("details", {})
    
    if not all([package_id, credits, amount, method]):
        return err("Missing required fields")
    
    try:
        # Process payment (simulated)
        success, transaction_id = process_payment(amount, method, details)
        
        if not success:
            return err("Payment processing failed", 400)
        
        # Add credits to user account
        new_total = add_credits(user_id, credits, f"purchase_{method}")
        
        return jsonify({
            "status": "success",
            "message": f"Added {credits} credits",
            "credits_added": credits,
            "total_credits": new_total,
            "transaction_id": transaction_id
        })
        
    except Exception as exc:
        log.error(f"Payment error: {exc}")
        return err("Payment failed", 500)


@app.route("/api/user/history", methods=["GET"])
@login_required
def get_user_history():
    """
    Get current user's query history.
    Headers: Authorization: Bearer <token>
    Returns: { "history": [...], "stats": {...} }
    """
    user_id = g.current_user.get("user_id")
    limit = request.args.get('limit', 10, type=int)
    
    try:
        history = get_query_history(user_id, limit)
        stats = get_user_stats(user_id)
        
        return jsonify({
            "status": "success",
            "history": history,
            "stats": stats
        })
    except Exception as exc:
        log.error(f"Get history error: {exc}")
        return err("Failed to get query history", 500)


# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=DEBUG, host="0.0.0.0", port=5000)