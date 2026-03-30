#!/usr/bin/env python3
"""
Test database connectivity and data.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import and test database
try:
    from sqlite_db import init_db, execute_query, get_table_stats, get_all_rows
    print("✅ Using SQLite database")
    
    # Initialize database
    print("🔧 Initializing database...")
    success = init_db()
    print(f"{'✅' if success else '❌'} Database init: {'Success' if success else 'Failed'}")
    
    if success:
        # Get stats
        stats = get_table_stats()
        print(f"📊 Database stats: {stats}")
        
        # Get sample data
        result = execute_query("SELECT * FROM products LIMIT 3")
        print(f"📋 Sample data ({result['count']} rows):")
        for row in result['rows']:
            print(f"  - {row['name']} ({row['category']}) - ${row['price']}")
    
except ImportError as e:
    print(f"❌ Import error: {e}")

print("\n🏥 Testing health endpoint...")
import requests
try:
    response = requests.get("http://localhost:5000/api/health")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Health check: {data}")
    else:
        print(f"❌ Health check failed: {response.status_code}")
except Exception as e:
    print(f"❌ Health check error: {e}")
