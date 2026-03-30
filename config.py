"""
config.py — Central configuration loaded from .env
Copy .env.example to .env and fill in your values before running.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ───────────────────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST",     "127.0.0.1")
DB_PORT     = int(os.getenv("DB_PORT", 5432))
DB_NAME     = os.getenv("DB_NAME",     "aidb")
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
TABLE_NAME  = "products"

# ── Anthropic ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"

# ── Flask ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
DEBUG      = os.getenv("FLASK_DEBUG", "false").lower() == "true"