# Question-Answering Backend API

## New Endpoint Added: `/api/ask`

A simple question-answering endpoint that processes natural language questions and returns direct answers with data.

### Usage

```bash
POST /api/ask
Content-Type: application/json

{
  "question": "What is the most expensive product?"
}
```

### Response Format

```json
{
  "answer": "The most expensive product is the Ergonomic Office Chair at $329.00.",
  "data": [
    {
      "id": 2,
      "name": "Ergonomic Office Chair",
      "category": "Furniture", 
      "price": 329.00,
      "stock": 12,
      "rating": 4.5,
      "description": "Lumbar-support mesh chair..."
    }
  ],
  "sql": "SELECT * FROM products ORDER BY price DESC LIMIT 1",
  "count": 1
}
```

### Features

- **Natural Language Processing**: Converts questions to SQL using Claude AI
- **Database Query**: Executes generated SQL on AlloyDB
- **Answer Generation**: Provides human-readable answers
- **Data Inclusion**: Returns raw data for further processing
- **SQL Transparency**: Shows generated SQL for debugging
- **Error Handling**: Graceful fallbacks for missing AI/DB

### Example Questions

1. "What is the most expensive product?"
2. "Show me all electronics under $100"
3. "Which products have the highest rating?"
4. "How many kitchen products are in stock?"
5. "What are the low stock items?"
6. "Show me sports products sorted by price"

### Error Responses

**Missing Question (400):**
```json
{
  "error": "Question is required."
}
```

**AI Not Configured (503):**
```json
{
  "error": "AI is not configured. Add ANTHROPIC_API_KEY to your .env file."
}
```

**Question Not Understood (422):**
```json
{
  "answer": "I couldn't understand your question: [error details]",
  "data": [],
  "sql": null
}
```

### Testing

Run the test script to verify functionality:

```bash
python test_ask_api.py
```

### Integration

This endpoint can be easily integrated with:
- Chat applications
- Voice assistants
- Mobile apps
- Other web services
- Data analysis tools

The endpoint provides both natural language answers and structured data, making it flexible for various use cases.
