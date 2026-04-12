"""
middleware.py — Flask middleware for rate limiting, logging, and request validation

Provides:
- Rate limiting per IP address
- Request/response logging
- API metrics collection
- Request size validation
- Security headers
"""

import time
import logging
from functools import wraps
from flask import request, g, jsonify
from collections import defaultdict
from typing import Optional

log = logging.getLogger(__name__)

# Rate limiting storage
_request_counts = defaultdict(list)  # ip -> list of timestamps
_rate_limits = {
    "default": (60, 100),  # (window_seconds, max_requests)
    "ask": (60, 30),       # Stricter limit for AI queries
    "query": (60, 20),     # Even stricter for SQL execution
    "execute": (60, 10),   # Very strict for raw SQL
}

# API metrics
_metrics = {
    "total_requests": 0,
    "total_errors": 0,
    "endpoint_counts": defaultdict(int),
    "response_times": [],
    "start_time": time.time()
}


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    @staticmethod
    def is_allowed(ip: str, endpoint: str = "default") -> tuple[bool, dict]:
        """Check if request is allowed and return rate limit info."""
        window, max_requests = _rate_limits.get(endpoint, _rate_limits["default"])
        
        now = time.time()
        key = f"{ip}:{endpoint}"
        
        # Clean old entries
        _request_counts[key] = [t for t in _request_counts[key] if now - t < window]
        
        # Check limit
        current_count = len(_request_counts[key])
        
        info = {
            "limit": max_requests,
            "remaining": max(0, max_requests - current_count - 1),
            "reset": window,
            "window": window
        }
        
        if current_count >= max_requests:
            return False, info
        
        # Record request
        _request_counts[key].append(now)
        return True, info


def rate_limit(endpoint_type: str = "default"):
    """Decorator to apply rate limiting to endpoints."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            allowed, info = RateLimiter.is_allowed(ip, endpoint_type)
            
            if not allowed:
                log.warning(f"Rate limit exceeded for {ip} on {endpoint_type}")
                return jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after": info["reset"],
                    "limit": info["limit"]
                }), 429
            
            # Add rate limit headers
            response = f(*args, **kwargs)
            if isinstance(response, tuple):
                response_obj, status_code = response
            else:
                response_obj = response
                status_code = 200
            
            # Set rate limit headers if it's a Response object
            if hasattr(response_obj, 'headers'):
                response_obj.headers['X-RateLimit-Limit'] = str(info['limit'])
                response_obj.headers['X-RateLimit-Remaining'] = str(info['remaining'])
            
            return response_obj if not isinstance(response, tuple) else (response_obj, status_code)
        
        return wrapper
    return decorator


def setup_middleware(app):
    """Configure all middleware for Flask app."""
    
    @app.before_request
    def before_request():
        """Process request before handling."""
        g.start_time = time.time()
        
        # Validate request size
        content_length = request.content_length
        if content_length and content_length > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({"error": "Request too large"}), 413
        
        # Validate content type for POST requests
        if request.method == 'POST':
            content_type = request.content_type or ''
            if not any(ct in content_type for ct in ['application/json', 'multipart/form-data', 'application/x-www-form-urlencoded']):
                return jsonify({"error": "Unsupported content type"}), 415
    
    @app.after_request
    def after_request(response):
        """Process response before sending."""
        # Calculate response time
        response_time = (time.time() - g.start_time) * 1000  # ms
        
        # Update metrics
        _metrics["total_requests"] += 1
        _metrics["response_times"].append(response_time)
        if response.status_code >= 400:
            _metrics["total_errors"] += 1
        _metrics["endpoint_counts"][request.endpoint or "unknown"] += 1
        
        # Keep only last 1000 response times
        if len(_metrics["response_times"]) > 1000:
            _metrics["response_times"] = _metrics["response_times"][-1000:]
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Add timing header
        response.headers['X-Response-Time'] = f"{response_time:.2f}ms"
        
        # Log request
        log.info(f"{request.method} {request.path} - {response.status_code} ({response_time:.1f}ms)")
        
        return response
    
    @app.errorhandler(404)
    def not_found(error):
        log.warning(f"404: {request.path}")
        return jsonify({"error": "Not found"}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        log.error(f"500: {str(error)}")
        return jsonify({"error": "Internal server error"}), 500
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        return jsonify({"error": "Too many requests"}), 429


def get_metrics() -> dict:
    """Get current API metrics."""
    uptime = time.time() - _metrics["start_time"]
    avg_response = sum(_metrics["response_times"]) / len(_metrics["response_times"]) if _metrics["response_times"] else 0
    
    return {
        "uptime_seconds": int(uptime),
        "total_requests": _metrics["total_requests"],
        "total_errors": _metrics["total_errors"],
        "error_rate": f"{(_metrics['total_errors'] / _metrics['total_requests'] * 100):.2f}%" if _metrics["total_requests"] > 0 else "0%",
        "avg_response_time_ms": f"{avg_response:.2f}",
        "requests_per_minute": f"{_metrics['total_requests'] / (uptime / 60):.1f}" if uptime > 0 else "0",
        "endpoint_breakdown": dict(_metrics["endpoint_counts"])
    }


def validate_request_schema(schema: dict):
    """Decorator to validate request JSON against a schema."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.is_json:
                data = request.get_json()
                missing_fields = [field for field, required in schema.items() if required and field not in data]
                if missing_fields:
                    return jsonify({"error": f"Missing required fields: {missing_fields}"}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator
