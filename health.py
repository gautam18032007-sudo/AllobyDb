"""
health.py — Health monitoring and database diagnostics

Provides:
- Database connection health checks
- Performance monitoring
- Connection pool statistics
- System resource monitoring
"""

import time
import logging
import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime

log = logging.getLogger(__name__)

# Health check results storage
_health_history = []
_max_history = 100


class HealthMonitor:
    """Monitor system and database health."""
    
    def __init__(self, db_type: str):
        self.db_type = db_type
        self.start_time = time.time()
        self.check_count = 0
        self.last_check = None
        self.status = "unknown"
    
    def check_database_health(self, get_conn_func) -> Dict[str, Any]:
        """Perform comprehensive database health check."""
        self.check_count += 1
        start = time.time()
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "db_type": self.db_type,
            "status": "healthy",
            "response_time_ms": 0,
            "checks": {}
        }
        
        try:
            # Test connection
            conn = get_conn_func()
            if hasattr(conn, '__enter__'):
                with conn as c:
                    result["checks"]["connection"] = self._test_connection(c)
                    result["checks"]["query_performance"] = self._test_query_performance(c)
                    result["checks"]["table_stats"] = self._get_table_stats(c)
            else:
                result["checks"]["connection"] = self._test_connection(conn)
                result["checks"]["query_performance"] = self._test_query_performance(conn)
                result["checks"]["table_stats"] = self._get_table_stats(conn)
            
            result["response_time_ms"] = (time.time() - start) * 1000
            self.status = "healthy"
            
        except Exception as e:
            result["status"] = "unhealthy"
            result["error"] = str(e)
            self.status = "unhealthy"
            log.error(f"Health check failed: {e}")
        
        self.last_check = result
        self._store_history(result)
        return result
    
    def _test_connection(self, conn) -> Dict[str, Any]:
        """Test basic database connectivity."""
        start = time.time()
        try:
            cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
            if self.db_type == "postgresql":
                cursor.execute("SELECT 1")
            else:
                cursor.execute("SELECT 1")
            
            response_time = (time.time() - start) * 1000
            return {
                "status": "ok",
                "response_time_ms": f"{response_time:.2f}"
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _test_query_performance(self, conn) -> Dict[str, Any]:
        """Test query execution performance."""
        start = time.time()
        try:
            cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
            
            # Test simple query
            if self.db_type == "postgresql":
                cursor.execute("SELECT COUNT(*) FROM products")
            else:
                cursor.execute("SELECT COUNT(*) FROM products")
            
            result = cursor.fetchone()
            response_time = (time.time() - start) * 1000
            
            return {
                "status": "ok",
                "response_time_ms": f"{response_time:.2f}",
                "row_count": result[0] if result else 0
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _get_table_stats(self, conn) -> Dict[str, Any]:
        """Get table statistics."""
        try:
            cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
            
            stats = {}
            if self.db_type == "postgresql":
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_rows,
                        pg_size_pretty(pg_total_relation_size('products')) as size
                    FROM products
                """)
                row = cursor.fetchone()
                stats = {
                    "total_rows": row[0],
                    "table_size": row[1]
                }
            else:
                cursor.execute("SELECT COUNT(*) as total_rows FROM products")
                row = cursor.fetchone()
                cursor.execute("PRAGMA page_count")
                pages = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                
                size_bytes = pages * page_size
                size_formatted = f"{size_bytes / 1024:.1f} KB" if size_bytes < 1024*1024 else f"{size_bytes / (1024*1024):.1f} MB"
                
                stats = {
                    "total_rows": row[0],
                    "table_size": size_formatted,
                    "pages": pages
                }
            
            return {"status": "ok", "stats": stats}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _store_history(self, result: Dict[str, Any]) -> None:
        """Store health check in history."""
        _health_history.append(result)
        if len(_health_history) > _max_history:
            _health_history.pop(0)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of health status."""
        uptime = time.time() - self.start_time
        
        # Calculate health score from recent history
        recent_checks = _health_history[-10:] if _health_history else []
        healthy_count = sum(1 for check in recent_checks if check.get("status") == "healthy")
        health_score = (healthy_count / len(recent_checks) * 100) if recent_checks else 100
        
        return {
            "overall_status": self.status,
            "health_score": f"{health_score:.1f}%",
            "uptime_seconds": int(uptime),
            "total_checks": self.check_count,
            "db_type": self.db_type,
            "last_check": self.last_check
        }
    
    def get_health_history(self, limit: int = 20) -> list:
        """Get health check history."""
        return _health_history[-limit:]


# Global health monitor instance
_health_monitor: Optional[HealthMonitor] = None


def init_health_monitor(db_type: str) -> HealthMonitor:
    """Initialize global health monitor."""
    global _health_monitor
    _health_monitor = HealthMonitor(db_type)
    return _health_monitor


def get_health_monitor() -> Optional[HealthMonitor]:
    """Get health monitor instance."""
    return _health_monitor


def check_system_resources() -> Dict[str, Any]:
    """Check system resource usage."""
    try:
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": {
                "total": f"{psutil.virtual_memory().total / (1024**3):.1f} GB",
                "available": f"{psutil.virtual_memory().available / (1024**3):.1f} GB",
                "percent_used": psutil.virtual_memory().percent
            },
            "disk": {
                "total": f"{psutil.disk_usage('/').total / (1024**3):.1f} GB",
                "used": f"{psutil.disk_usage('/').used / (1024**3):.1f} GB",
                "percent_used": psutil.disk_usage('/').percent
            }
        }
    except ImportError:
        return {"error": "psutil not installed"}
