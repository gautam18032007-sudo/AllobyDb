"""
credits.py — Credit system for query usage and payments

Provides:
- User credit tracking (200 free on signup)
- Anonymous usage tracking (2 free queries per IP)
- Credit deduction on queries
- Payment integration (UPI, Cards)
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)

# Constants
FREE_CREDITS_ON_SIGNUP = 200
FREE_QUERIES_ANONYMOUS = 2
CREDITS_PER_QUERY = 1

# Anonymous tracking file
ANONYMOUS_USAGE_FILE = "anonymous_usage.json"

# In-memory storage for credits and query history (use database in production)
_user_credits = {}
_user_query_history = {}


def _load_anonymous_usage() -> Dict[str, int]:
    """Load anonymous usage tracking from file."""
    if os.path.exists(ANONYMOUS_USAGE_FILE):
        try:
            with open(ANONYMOUS_USAGE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def _save_anonymous_usage(data: Dict[str, int]):
    """Save anonymous usage tracking to file."""
    try:
        with open(ANONYMOUS_USAGE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        log.error(f"Failed to save anonymous usage: {e}")


def check_anonymous_quota(ip_address: str) -> tuple[bool, int]:
    """
    Check if anonymous user can make a query.
    Returns (allowed, remaining_queries)
    """
    usage = _load_anonymous_usage()
    used = usage.get(ip_address, 0)
    remaining = max(0, FREE_QUERIES_ANONYMOUS - used)
    return remaining > 0, remaining


def record_anonymous_usage(ip_address: str) -> int:
    """Record anonymous query usage. Returns remaining queries."""
    usage = _load_anonymous_usage()
    usage[ip_address] = usage.get(ip_address, 0) + 1
    _save_anonymous_usage(usage)
    return max(0, FREE_QUERIES_ANONYMOUS - usage[ip_address])


def get_user_credits(user_id: int) -> int:
    """Get user's available credits."""
    return _user_credits.get(user_id, 0)


def add_credits(user_id: int, amount: int, reason: str = "purchase") -> int:
    """Add credits to user account."""
    current = _user_credits.get(user_id, 0)
    new_total = current + amount
    _user_credits[user_id] = new_total
    log.info(f"Added {amount} credits to user {user_id}. Reason: {reason}. Total: {new_total}")
    return new_total


def deduct_credits(user_id: int, amount: int = CREDITS_PER_QUERY) -> tuple[bool, int]:
    """
    Deduct credits for query.
    Returns (success, remaining_credits)
    """
    current = _user_credits.get(user_id, 0)
    if current < amount:
        return False, current
    
    new_total = current - amount
    _user_credits[user_id] = new_total
    return True, new_total


def initialize_user_credits(user_id: int) -> int:
    """Initialize new user with free signup credits."""
    if user_id not in _user_credits:
        _user_credits[user_id] = FREE_CREDITS_ON_SIGNUP
        log.info(f"Initialized user {user_id} with {FREE_CREDITS_ON_SIGNUP} free credits")
        return FREE_CREDITS_ON_SIGNUP
    return _user_credits[user_id]


# Payment processing (simulated - integrate with real payment gateway)
def process_payment(amount: int, method: str, details: Dict) -> tuple[bool, str]:
    """
    Process payment for credits.
    Returns (success, transaction_id)
    """
    # This is a placeholder - integrate with Razorpay, Stripe, etc.
    try:
        # Simulate payment processing
        transaction_id = f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(str(details)) % 10000}"
        log.info(f"Payment processed: {amount} credits via {method}, TXN: {transaction_id}")
        return True, transaction_id
    except Exception as e:
        log.error(f"Payment failed: {e}")
        return False, ""


# Credit packages (One-time purchase)
CREDIT_PACKAGES = [
    {"id": "basic", "credits": 100, "price_inr": 49, "label": "Basic", "icon": "⚡"},
    {"id": "standard", "credits": 500, "price_inr": 199, "label": "Standard", "popular": True, "icon": "🔥"},
    {"id": "premium", "credits": 2000, "price_inr": 699, "label": "Premium", "icon": "💎"},
    {"id": "enterprise", "credits": 10000, "price_inr": 2999, "label": "Enterprise", "icon": "🏢"},
]

# Subscription plans (Monthly recurring)
SUBSCRIPTION_PLANS = [
    {"id": "starter", "credits_per_month": 500, "price_inr": 149, "label": "Starter", "icon": "🚀"},
    {"id": "pro", "credits_per_month": 2000, "price_inr": 499, "label": "Pro", "popular": True, "icon": "⭐"},
    {"id": "business", "credits_per_month": 10000, "price_inr": 1999, "label": "Business", "icon": "💼"},
]

# In-memory subscription storage
_user_subscriptions = {}
_user_last_daily_bonus = {}


def get_credit_packages() -> list:
    """Get available credit packages."""
    return CREDIT_PACKAGES


def get_subscription_plans() -> list:
    """Get available subscription plans."""
    return SUBSCRIPTION_PLANS


def check_daily_bonus(user_id: int) -> tuple[bool, int]:
    """
    Check if user can claim daily bonus.
    Returns (can_claim, bonus_amount)
    """
    from datetime import datetime, timedelta
    
    last_claim = _user_last_daily_bonus.get(user_id)
    now = datetime.now()
    
    if last_claim:
        last_claim_dt = datetime.fromisoformat(last_claim)
        if (now - last_claim_dt) < timedelta(hours=24):
            return False, 0
    
    return True, 10  # 10 free credits daily


def claim_daily_bonus(user_id: int) -> int:
    """Claim daily bonus credits. Returns credits added."""
    can_claim, bonus = check_daily_bonus(user_id)
    
    if can_claim:
        _user_last_daily_bonus[user_id] = datetime.now().isoformat()
        current = _user_credits.get(user_id, 0)
        _user_credits[user_id] = current + bonus
        log.info(f"User {user_id} claimed daily bonus: {bonus} credits")
        return bonus
    
    return 0


def get_subscription_credits(user_id: int) -> int:
    """Get monthly credits from subscription plan."""
    sub = _user_subscriptions.get(user_id)
    if sub:
        plan = next((p for p in SUBSCRIPTION_PLANS if p["id"] == sub["plan_id"]), None)
        if plan:
            return plan["credits_per_month"]
    return 0


def subscribe_user(user_id: int, plan_id: str) -> bool:
    """Subscribe user to a plan."""
    plan = next((p for p in SUBSCRIPTION_PLANS if p["id"] == plan_id), None)
    if not plan:
        return False
    
    _user_subscriptions[user_id] = {
        "plan_id": plan_id,
        "started_at": datetime.now().isoformat(),
        "credits_added_this_month": False
    }
    
    # Add first month credits immediately
    current = _user_credits.get(user_id, 0)
    _user_credits[user_id] = current + plan["credits_per_month"]
    
    log.info(f"User {user_id} subscribed to {plan_id} plan")
    return True


def get_user_subscription(user_id: int) -> Optional[Dict]:
    """Get user's current subscription."""
    return _user_subscriptions.get(user_id)


def record_query(user_id: int, query: str, sql: str = None, success: bool = True) -> None:
    """Record a query in user's history."""
    if user_id not in _user_query_history:
        _user_query_history[user_id] = []
    
    _user_query_history[user_id].append({
        "query": query,
        "sql": sql,
        "success": success,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep only last 50 queries
    if len(_user_query_history[user_id]) > 50:
        _user_query_history[user_id] = _user_query_history[user_id][-50:]


def get_query_history(user_id: int, limit: int = 10) -> list:
    """Get user's query history."""
    history = _user_query_history.get(user_id, [])
    return history[-limit:][::-1]  # Return most recent first


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Get user statistics including total queries and credits."""
    history = _user_query_history.get(user_id, [])
    successful = sum(1 for q in history if q.get("success", True))
    
    return {
        "total_queries": len(history),
        "successful_queries": successful,
        "failed_queries": len(history) - successful,
        "credits_remaining": get_user_credits(user_id),
        "credits_used": sum(1 for q in history if q.get("success", True))  # Each successful query uses 1 credit
    }
