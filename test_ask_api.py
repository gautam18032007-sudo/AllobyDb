#!/usr/bin/env python3
"""
Test script for the /api/ask question-answering endpoint.
"""

import requests
import json

# Base URL of the Flask application
BASE_URL = "http://localhost:5000"

def test_ask_endpoint():
    """Test the /api/ask endpoint with various questions."""
    
    test_questions = [
        "What is the most expensive product?",
        "Show me all electronics under $100",
        "Which products have the highest rating?",
        "How many kitchen products are in stock?",
        "What are the low stock items?",
        "Show me sports products sorted by price"
    ]
    
    print("🤖 Testing /api/ask Question-Answering Endpoint")
    print("=" * 50)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{i}. Question: {question}")
        print("-" * 40)
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/ask",
                json={"question": question},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Answer: {data.get('answer', 'No answer')}")
                print(f"📊 Results: {data.get('count', 0)} rows")
                if data.get('sql'):
                    print(f"🔍 SQL: {data['sql']}")
            else:
                print(f"❌ Error ({response.status_code}): {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection error - is the server running?")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

def test_health_endpoint():
    """Test the health endpoint to check system status."""
    print("\n🏥 Checking System Health")
    print("-" * 30)
    
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data.get('status')}")
            print(f"🗄️  Database: {'✅ Ready' if data.get('db_ready') else '❌ Not ready'}")
            print(f"🤖 AI: {'✅ Ready' if data.get('ai_ready') else '❌ Not configured'}")
            print(f"📋 Table: {data.get('table')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

if __name__ == "__main__":
    test_health_endpoint()
    test_ask_endpoint()
