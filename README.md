# AlloyDB AI Query Interface

A modern web application that demonstrates natural language querying of a product database using AI-powered SQL generation.

## 🚀 Features

- **Natural Language to SQL**: Convert plain English questions into SQL queries
- **AI-Powered**: Uses Claude AI for intelligent query generation and summarization
- **Modern UI**: Dark-themed interface with sidebar navigation
- **Multiple Views**: Query, Browse, Schema, and AI Chatbot tabs
- **REST API**: Full backend API for programmatic access
- **Database Support**: SQLite (demo) with PostgreSQL/AlloyDB upgrade path
- **Real-time Results**: Instant query execution with formatted results

## 📊 Demo Database

The application includes a sample product database with:
- **20 products** across 5 categories
- **Electronics, Kitchen, Sports, Furniture, Home**
- **Price range**: $19.99 - $329.00
- **Stock levels**: 12-150 units
- **Customer ratings**: 4.2 - 4.9

## 🛠️ Technology Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend**: Python Flask
- **Database**: SQLite (demo) / PostgreSQL / AlloyDB
- **AI**: Anthropic Claude Sonnet 4
- **API**: RESTful JSON endpoints

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/AlloyDB.git
   cd AlloyDB
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   - Web UI: http://localhost:5000
   - API Health: http://localhost:5000/api/health

## 📖 Usage Examples

### Natural Language Questions
- "What is the most expensive product?"
- "Show me electronics under $100"
- "Which products have the highest rating?"
- "What are the low stock items?"
- "How many kitchen products are there?"

### API Usage

```bash
# Ask a question
curl -X POST http://localhost:5000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me electronics under $100"}'

# Get database stats
curl http://localhost:5000/api/stats

# Browse all products
curl http://localhost:5000/api/browse
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file:
```env
# Database (SQLite works by default)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=aidb
DB_USER=postgres
DB_PASSWORD=postgres

# Anthropic API (optional - demo mode works without it)
ANTHROPIC_API_KEY=your_api_key_here

# Flask
FLASK_SECRET_KEY=your-secret-key
FLASK_DEBUG=true
```

### Database Options

1. **SQLite (Demo)**: Works out of the box, no setup required
2. **PostgreSQL**: Install PostgreSQL and update connection settings
3. **AlloyDB**: Use Google Cloud AlloyDB for production

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/stats` | Database statistics |
| GET | `/api/schema` | Table schema |
| GET | `/api/browse` | All products |
| POST | `/api/query` | Full NL→SQL pipeline |
| POST | `/api/ask` | Simple Q&A |
| POST | `/api/chat` | AI chatbot |

## 🎯 AI Features

### Demo Mode (No API Key)
- Pattern-based NL→SQL conversion
- Predefined question templates
- Simple result summarization

### Full AI Mode (With Anthropic Key)
- Advanced natural language understanding
- Complex SQL generation
- Intelligent result summarization
- Multi-turn chat conversations

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web UI        │    │   Flask API     │    │   Database      │
│                 │◄──►│                 │◄──►│                 │
│ - Query Input   │    │ - /api/ask      │    │ - Products      │
│ - Results Table │    │ - /api/query    │    │ - SQLite/PG     │
│ - Chat Bot      │    │ - /api/chat     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   AI Layer      │
                       │                 │
                       │ - Claude AI     │
                       │ - NL→SQL        │
                       │ - Summarization │
                       └─────────────────┘
```

## 🧪 Testing

Run the test suite:
```bash
python test_ask_api.py
```

## 📝 Development

### Project Structure
```
AlloyDB/
├── app.py              # Flask application
├── db.py               # PostgreSQL database layer
├── sqlite_db.py        # SQLite database layer
├── ai.py               # Claude AI integration
├── demo_ai.py          # Demo AI (no API key)
├── config.py           # Configuration
├── templates/
│   └── index.html      # Web UI
├── requirements.txt    # Dependencies
├── test_ask_api.py    # Test suite
└── README.md          # This file
```

### Adding New Features

1. **Database Schema**: Modify `db.py` or `sqlite_db.py`
2. **AI Prompts**: Update prompts in `ai.py` or `demo_ai.py`
3. **UI Components**: Edit `templates/index.html`
4. **API Endpoints**: Add routes in `app.py`

## 🚀 Deployment

### Production Setup

1. **Environment**: Set production environment variables
2. **Database**: Use PostgreSQL or AlloyDB
3. **AI**: Add Anthropic API key
4. **Security**: Update secret keys and enable HTTPS
5. **Scaling**: Consider containerization with Docker

### Docker Deployment

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Anthropic** - Claude AI for natural language processing
- **Flask** - Web framework
- **PostgreSQL** - Database technology
- **Google Cloud** - AlloyDB database service

## 📞 Support

For questions and support:
- Create an issue on GitHub
- Check the API documentation
- Review the test examples

---

**Built with ❤️ for demonstrating AI-powered database querying**
