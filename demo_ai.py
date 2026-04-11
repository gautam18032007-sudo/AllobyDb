"""
demo_ai.py — Demo AI layer that provides mock responses when no API key is configured
"""

import logging

log = logging.getLogger(__name__)

def nl_to_sql(question: str) -> dict:
    """
    Demo version: convert natural language to SQL with predefined patterns.
    Returns {"sql": "...", "error": None} or {"sql": None, "error": "..."}
    """
    question_lower = question.lower()
    
    # Predefined SQL patterns for common questions
    patterns = {
        "most expensive": "SELECT * FROM products ORDER BY price DESC LIMIT 1",
        "cheapest": "SELECT * FROM products ORDER BY price ASC LIMIT 1",
        "highest rating": "SELECT * FROM products ORDER BY rating DESC LIMIT 5",
        "top 5 highest rated": "SELECT * FROM products ORDER BY rating DESC LIMIT 5",
        "top rated": "SELECT * FROM products ORDER BY rating DESC LIMIT 5",
        "lowest rating": "SELECT * FROM products ORDER BY rating ASC LIMIT 1",
        "electronics": "SELECT * FROM products WHERE category = 'Electronics' ORDER BY price",
        "kitchen": "SELECT * FROM products WHERE category = 'Kitchen' ORDER BY price",
        "sports": "SELECT * FROM products WHERE category = 'Sports' ORDER BY price",
        "furniture": "SELECT * FROM products WHERE category = 'Furniture' ORDER BY price",
        "home": "SELECT * FROM products WHERE category = 'Home' ORDER BY price",
        "under $100": "SELECT * FROM products WHERE price < 100 ORDER BY price",
        "under 100": "SELECT * FROM products WHERE price < 100 ORDER BY price",
        "low stock": "SELECT * FROM products WHERE stock < 20 ORDER BY stock",
        "all products": "SELECT * FROM products ORDER BY name",
        "how many": "SELECT COUNT(*) as total, category FROM products GROUP BY category",
        "total stock": "SELECT SUM(stock) as total_stock FROM products",
    }

    # Check for simple patterns first
    for pattern, sql in patterns.items():
        if pattern in question_lower:
            return {"sql": sql, "error": None}

    # Check for price range (between $X and $Y)
    import re
    price_range = re.search(r'between\s+\$?(\d+)\s+and\s+\$?(\d+)', question_lower)
    if price_range:
        low, high = price_range.groups()
        return {"sql": f"SELECT * FROM products WHERE price BETWEEN {low} AND {high} ORDER BY price", "error": None}

    # Check for rating comparisons
    rating_above = re.search(r'rating\s+(above|over|>|greater\s+than)\s+(\d+\.?\d*)', question_lower)
    if rating_above:
        rating = rating_above.group(2)
        return {"sql": f"SELECT * FROM products WHERE rating > {rating} ORDER BY rating DESC", "error": None}

    rating_below = re.search(r'rating\s+(below|under|<|less\s+than)\s+(\d+\.?\d*)', question_lower)
    if rating_below:
        rating = rating_below.group(2)
        return {"sql": f"SELECT * FROM products WHERE rating < {rating} ORDER BY rating", "error": None}

    # Check for price comparisons
    price_above = re.search(r'price\s+(above|over|>|greater\s+than)\s+\$?(\d+)', question_lower)
    if price_above:
        price = price_above.group(2)
        return {"sql": f"SELECT * FROM products WHERE price > {price} ORDER BY price", "error": None}

    price_below = re.search(r'price\s+(below|under|<|less\s+than)\s+\$?(\d+)', question_lower)
    if price_below:
        price = price_below.group(2)
        return {"sql": f"SELECT * FROM products WHERE price < {price} ORDER BY price", "error": None}

    # Default fallback
    return {
        "sql": None,
        "error": "I can only answer questions about products, prices, categories, stock, and ratings. Try asking about 'most expensive', 'electronics under $100', or 'low stock items'."
    }

def summarise(question: str, rows: list, count: int) -> str:
    """
    Demo version: generate simple summaries based on query results.
    """
    if count == 0:
        return "No products match your query."
    
    if count == 1:
        row = rows[0]
        return f"Found 1 product: {row['name']} ({row['category']}) - ${row['price']} with {row['stock']} in stock and rating {row['rating']}."
    
    # Generate summary based on question type
    question_lower = question.lower()
    
    if "most expensive" in question_lower:
        row = rows[0]
        return f"The most expensive product is {row['name']} at ${row['price']}."
    
    if "cheapest" in question_lower:
        row = rows[0]
        return f"The cheapest product is {row['name']} at ${row['price']}."
    
    if "top 5 highest rated" in question_lower or "top rated" in question_lower:
        if count == 5:
            return f"Here are the top 5 highest rated products:\n1. {rows[0]['name']} - Rating: {rows[0]['rating']}\n2. {rows[1]['name']} - Rating: {rows[1]['rating']}\n3. {rows[2]['name']} - Rating: {rows[2]['rating']}\n4. {rows[3]['name']} - Rating: {rows[3]['rating']}\n5. {rows[4]['name']} - Rating: {rows[4]['rating']}"
        else:
            return f"Found {count} top-rated products, led by {rows[0]['name']} with a rating of {rows[0]['rating']}."
    
    if "highest rating" in question_lower:
        row = rows[0]
        return f"The highest rated product is {row['name']} with a rating of {row['rating']}."
    
    if "electronics" in question_lower:
        return f"Found {count} electronics products ranging from ${rows[0]['price']} to ${rows[-1]['price']}."
    
    if "under $100" in question_lower or "under 100" in question_lower:
        return f"Found {count} products under $100, with prices ranging from ${rows[0]['price']} to ${rows[-1]['price']}."

    # Price range queries
    if "between" in question_lower and ("$" in question_lower or any(str(i) in question_lower for i in range(10))):
        if count > 0:
            prices = [r['price'] for r in rows]
            return f"Found {count} products in this price range, from ${min(prices):.2f} to ${max(prices):.2f}."
        else:
            return "No products found in this price range."

    # Rating comparison queries
    if "rating" in question_lower and any(op in question_lower for op in ["above", ">", "over", "greater"]):
        if count > 0:
            return f"Found {count} products with rating above the threshold, led by {rows[0]['name']} with {rows[0]['rating']} rating."
        else:
            return "No products found with rating above that threshold."

    if "low stock" in question_lower:
        items = ", ".join([f"{row['name']} ({row['stock']})" for row in rows[:3]])
        return f"Found {count} low stock items: {items}{'...' if count > 3 else ''}."
    
    if "how many" in question_lower:
        return f"Found {count} products total across the database."
    
    # Generic summary
    return f"Found {count} products matching your query."

def chat(messages: list) -> str:
    """
    Demo version: simple chatbot responses.
    """
    if not messages:
        return "Hello! I'm DataBot, your demo AI assistant. I can help you query the product database."
    
    last_message = messages[-1].get("content", "").lower()
    
    if "hello" in last_message or "hi" in last_message:
        return "Hello! I'm DataBot. You can ask me about products, prices, categories, stock levels, or ratings."
    
    if "what data" in last_message or "what products" in last_message:
        return "I have access to a product database with 20 products across 5 categories: Electronics, Kitchen, Sports, Furniture, and Home. Each product has price, stock, rating, and description information."
    
    if "how does it work" in last_message:
        return "I convert your natural language questions into SQL queries, execute them on the database, and provide you with the results in plain English. Try asking 'What is the most expensive product?'"
    
    if "example" in last_message or "sample" in last_message:
        return "Try these questions: 'Show me electronics under $100', 'What are the low stock items?', 'Which products have the highest rating?', or 'How many kitchen products are there?'"
    
    return "I'm a demo AI assistant. I can help you query the product database. Try asking about products, prices, categories, stock, or ratings."

def validate_sql(sql: str) -> dict:
    """
    Simple SQL validation for demo purposes.
    """
    sql_upper = sql.upper()
    
    if not sql.strip().startswith("SELECT"):
        return {"ok": False, "reason": "Only SELECT queries are allowed"}
    
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
    for word in forbidden:
        if word in sql_upper:
            return {"ok": False, "reason": f"Forbidden keyword: {word}"}
    
    return {"ok": True}
