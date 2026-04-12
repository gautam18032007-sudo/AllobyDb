"""
auth.py — User authentication system with email login

Provides:
- User registration with email/password
- Secure password hashing with bcrypt
- Secure token-based authentication
- Session management
- Password validation and security
"""

import re
import bcrypt
import logging
import secrets
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import request, g

from config import SECRET_KEY

log = logging.getLogger(__name__)

# Token Configuration
TOKEN_EXPIRATION_HOURS = 24


class AuthError(Exception):
    """Custom exception for authentication errors."""
    pass


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# In-memory token storage (in production, use Redis or database)
_active_tokens = {}

def generate_token(user_id: int, email: str) -> str:
    """Generate secure token for user."""
    # Create a secure random token
    token = secrets.token_urlsafe(32)
    
    # Store token data
    _active_tokens[token] = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS),
        'created': datetime.utcnow()
    }
    
    return token


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate token."""
    if token not in _active_tokens:
        return None
    
    data = _active_tokens[token]
    
    # Check expiration
    if datetime.utcnow() > data['exp']:
        del _active_tokens[token]
        log.warning("Token has expired")
        return None
    
    return {
        'user_id': data['user_id'],
        'email': data['email']
    }


def invalidate_token(token: str) -> bool:
    """Invalidate a token (logout)."""
    if token in _active_tokens:
        del _active_tokens[token]
        return True
    return False


def get_auth_token() -> Optional[str]:
    """Extract token from request headers."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


def login_required(f):
    """Decorator to require authentication for endpoints."""
    from functools import wraps
    
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_auth_token()
        
        if not token:
            from flask import jsonify
            return jsonify({"error": "Authentication required"}), 401
        
        payload = decode_token(token)
        if not payload:
            from flask import jsonify
            return jsonify({"error": "Invalid or expired token"}), 401
        
        # Set current user in flask g
        g.current_user = payload
        return f(*args, **kwargs)
    
    return decorated


def register_user(conn, email: str, password: str, name: str = "") -> Dict[str, Any]:
    """
    Register a new user.
    Returns user data or raises AuthError.
    """
    # Validate email
    if not validate_email(email):
        raise AuthError("Invalid email format")
    
    # Validate password
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        raise AuthError(error_msg)
    
    cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
    
    # Check if email already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        raise AuthError("Email already registered")
    
    # Hash password
    password_hash = hash_password(password)
    
    # Insert user
    cursor.execute(
        "INSERT INTO users (email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
        (email, password_hash, name, datetime.utcnow().isoformat())
    )
    
    # Get user ID
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user_id = cursor.fetchone()[0]
    
    log.info(f"User registered: {email}")
    
    return {
        "id": user_id,
        "email": email,
        "name": name
    }


def authenticate_user(conn, email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate user with email and password.
    Returns user data with token or None.
    """
    cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
    
    # Get user by email
    cursor.execute(
        "SELECT id, email, password_hash, name FROM users WHERE email = ?",
        (email,)
    )
    row = cursor.fetchone()
    
    if not row:
        log.warning(f"Login attempt for non-existent user: {email}")
        return None
    
    user_id, user_email, password_hash, name = row
    
    # Verify password
    if not verify_password(password, password_hash):
        log.warning(f"Failed login attempt for user: {email}")
        return None
    
    # Generate token
    token = generate_token(user_id, user_email)
    
    log.info(f"User authenticated: {email}")
    
    return {
        "id": user_id,
        "email": user_email,
        "name": name,
        "token": token
    }


def get_user_by_id(conn, user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID (excluding password)."""
    cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
    
    cursor.execute(
        "SELECT id, email, name, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "email": row[1],
        "name": row[2],
        "created_at": row[3]
    }


# SQL to create users table
CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""

CREATE_USERS_TABLE_SQL_POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""
