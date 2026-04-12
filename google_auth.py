"""
google_auth.py — Google OAuth authentication

Provides:
- Google Sign-In integration
- OAuth2 flow handling
- User info retrieval from Google
"""

import logging
import requests
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)

# Google OAuth configuration
# Note: In production, store these in environment variables
GOOGLE_CLIENT_ID = "your-google-client-id.apps.googleusercontent.com"  # Replace with actual
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def verify_google_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Google ID token and return user info.
    """
    try:
        # Verify token with Google
        response = requests.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token},
            timeout=10
        )
        
        if response.status_code != 200:
            log.error(f"Google token verification failed: {response.text}")
            return None
        
        token_info = response.json()
        
        # Check if token is valid and not expired
        if token_info.get("error"):
            log.error(f"Token error: {token_info['error']}")
            return None
        
        # Get user info using access token
        # For now, extract info from ID token
        user_info = {
            "sub": token_info.get("sub"),  # Google user ID
            "email": token_info.get("email"),
            "email_verified": token_info.get("email_verified"),
            "name": token_info.get("name"),
            "picture": token_info.get("picture"),
            "given_name": token_info.get("given_name"),
            "family_name": token_info.get("family_name"),
        }
        
        if not user_info["email"] or not user_info["email_verified"]:
            log.warning("Email not verified or missing")
            return None
        
        return user_info
        
    except Exception as e:
        log.error(f"Error verifying Google token: {e}")
        return None


def get_or_create_user(conn, google_user_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get existing user or create new one from Google info.
    Returns user data.
    """
    email = google_user_info["email"]
    google_id = google_user_info["sub"]
    name = google_user_info.get("name", "")
    picture = google_user_info.get("picture", "")
    
    cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
    
    # Check if user exists
    cursor.execute("SELECT id, name FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    
    if row:
        # Existing user - update last login
        user_id, existing_name = row
        cursor.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        is_new = False
        display_name = existing_name or name
    else:
        # New user - create account
        cursor.execute(
            """INSERT INTO users (email, password_hash, name, created_at) 
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (email, "google_oauth", name)  # password_hash not used for OAuth
        )
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user_id = cursor.fetchone()[0]
        is_new = True
        display_name = name
    
    return {
        "id": user_id,
        "email": email,
        "name": display_name,
        "picture": picture,
        "is_new": is_new
    }
