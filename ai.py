"""
ai.py — Server-side AI layer using Anthropic Claude

Three functions:
  1. nl_to_sql()        – converts natural language → safe SELECT SQL
  2. summarise()        – converts query results → plain-English summary
  3. chat()             – general AI chatbot about the database / products
  4. validate_sql()     – safety gate: blocks non-SELECT statements
"""

import re
import logging
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from db import get_schema_text

log = logging.getLogger(__name__)

# Initialise Anthropic client once
_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ── SQL safety validation ──────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|"
    r"EXEC|EXECUTE|COPY|VACUUM|CLUSTER|COMMENT|LOCK|CALL|MERGE)\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> dict:
    """
    Returns {"ok": True} or {"ok": False, "reason": "..."}.
    Enforces SELECT-only, no stacked queries.
    """
    s = sql.strip()
    if not s:
        return {"ok": False, "reason": "Empty SQL."}

    first = s.split()[0].upper()
    if first != "SELECT":
        return {"ok": False, "reason": f"Only SELECT is allowed (got {first})."}

    m = _FORBIDDEN.search(s)
    if m:
        return {"ok": False, "reason": f"Forbidden keyword: {m.group().upper()}"}

    if ";" in s:
        return {"ok": False, "reason": "Semicolons are not permitted (prevents stacked queries)."}

    return {"ok": True, "reason": None}


# ── NL → SQL ──────────────────────────────────────────────────────────────

_NL2SQL_SYSTEM = """You are an expert PostgreSQL query generator for a product database.

{schema}

STRICT RULES — follow exactly or the app will break:
1. Output ONLY the raw SQL SELECT statement. Nothing else.
2. No markdown, no code fences (```), no semicolons, no explanation.
3. Use ONLY the columns listed in the schema above.
4. Always add LIMIT 50 unless the user explicitly asks for more.
5. Use ILIKE for case-insensitive text matching.
6. For "most expensive per category" use: SELECT DISTINCT ON (category) ...
7. If the question cannot be answered from this schema, output exactly:
   CANNOT_ANSWER
8. Never output anything except valid SQL or CANNOT_ANSWER."""


def nl_to_sql(question: str) -> dict:
    """
    Convert natural language question → SQL SELECT.
    Returns {"sql": "...", "error": None} or {"sql": None, "error": "..."}.
    """
    schema = get_schema_text()
    system = _NL2SQL_SYSTEM.format(schema=schema)

    try:
        resp = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        raw = resp.content[0].text.strip()

        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:sql)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
        raw = raw.rstrip(";")

        if raw.upper().startswith("CANNOT_ANSWER"):
            return {
                "sql": None,
                "error": (
                    "I couldn't map your question to this database. "
                    "Try asking about products, prices, categories, "
                    "stock levels, or ratings."
                ),
            }

        check = validate_sql(raw)
        if not check["ok"]:
            return {"sql": None, "error": f"Generated SQL failed safety check: {check['reason']}"}

        return {"sql": raw, "error": None}

    except ValueError as exc:
        return {"sql": None, "error": str(exc)}
    except anthropic.AuthenticationError:
        return {"sql": None, "error": "Invalid Anthropic API key. Check your .env file."}
    except anthropic.RateLimitError:
        return {"sql": None, "error": "Anthropic rate limit reached. Wait a moment and try again."}
    except Exception as exc:
        log.error(f"nl_to_sql error: {exc}")
        return {"sql": None, "error": f"AI error: {exc}"}


# ── Result summariser ──────────────────────────────────────────────────────

_SUMM_SYSTEM = """You are a helpful data analyst assistant.
Given a question and query results from a product database, write a clear,
concise 2-3 sentence answer that directly addresses the question.
- Include specific product names, numbers, prices, and ratings from the data.
- If there are no results, say so clearly and suggest a rephrasing.
- Be factual and precise. Do not guess beyond what the data shows."""


def summarise(question: str, rows: list, count: int) -> str:
    """Return a plain-English summary of query results."""
    if count == 0:
        return "No products matched your query. Try broadening the criteria."

    sample = rows[:15]
    user_msg = (
        f"Question: {question}\n\n"
        f"Total results: {count}\n"
        f"Data:\n{sample}"
    )
    try:
        resp = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            system=_SUMM_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        log.error(f"summarise error: {exc}")
        return f"Found {count} result(s)."


# ── Chatbot ────────────────────────────────────────────────────────────────

_CHAT_SYSTEM = """You are DataBot, an AI assistant for the AlloyDB product database demo.

{schema}

You help users by:
1. Answering questions about the product data (prices, categories, stock, ratings).
2. Explaining how to query the database using natural language.
3. Suggesting example questions users can ask.
4. Explaining the AlloyDB + AI architecture of this application.
5. Providing data insights and analysis.

Keep answers concise and friendly. If the user asks a question you can answer
from the schema/data context, do so. If they ask something unrelated to the
database or app, politely redirect them.

Architecture context:
- Frontend: HTML/CSS/JS served by Flask
- Backend: Python Flask REST API
- Database: AlloyDB for PostgreSQL (Google Cloud)
- AI: Anthropic Claude ({model}) for NL→SQL and summarisation
- The app converts plain English questions → SQL → executes on AlloyDB → AI summary"""


def chat(messages: list) -> str:
    """
    Multi-turn chatbot. `messages` is a list of {"role": "user"|"assistant", "content": "..."}.
    Returns the assistant reply string.
    """
    schema = get_schema_text()
    system = _CHAT_SYSTEM.format(schema=schema, model=CLAUDE_MODEL)

    try:
        resp = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=system,
            messages=messages,
        )
        return resp.content[0].text.strip()
    except ValueError as exc:
        return f"Configuration error: {exc}"
    except anthropic.AuthenticationError:
        return "Invalid API key. Please check your .env file and restart the server."
    except anthropic.RateLimitError:
        return "Rate limit reached. Please wait a moment before sending another message."
    except Exception as exc:
        log.error(f"chat error: {exc}")
        return f"Sorry, I encountered an error: {exc}"