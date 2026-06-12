# 🤖 AI Assist — AI-Powered Chatbot Web Application

A production-style, intelligent chatbot web application built with **Python Flask**, **SQLite**, and **Natural Language Processing**. Supports contextual conversations, semantic intent matching, chat history, and an admin analytics dashboard.

## ✨ Features

### 🧠 AI / NLP Engine
- **Intent recognition** via semantic similarity (sentence-transformers / TF-IDF fallback)
- **Contextual conversations** — remembers last exchange for follow-ups ("And on Sunday?")
- **Confidence scoring** — thresholds for high/medium/low confidence responses
- **Preprocessing pipeline** — tokenization, lemmatization, stopword removal (NLTK)
- **Rich FAQ dataset** — 18+ intents covering greetings, services, pricing, support, security, etc.

### 🌐 Backend (Flask)
- RESTful API endpoints: `POST /api/chat`, `GET /api/history`, `DELETE /api/clear-history`
- SQLite database with `users`, `chat_sessions`, `messages`, and `logs` tables
- **Rate limiting** via Flask-Limiter
- **Input sanitization** — XSS protection, HTML escaping, length limits
- **Session management** — persistent user/session tracking
- **CORS** enabled for cross-origin requests

### 🎨 Frontend
- **Futuristic dark-mode UI** with glassmorphism, neon accents, and animated orb backgrounds
- **ChatGPT-inspired** chat interface with smooth animations
- **Typing indicator** with animated dots
- **Suggestion chips** for quick FAQ access
- **Mobile-responsive** with sidebar drawer
- **Auto-scroll** and animated message appearance

### 📊 Admin Dashboard
- Real-time analytics: total users, messages, avg. messages/user, active days
- **Activity graph** — 7-day message volume visualization
- **Most asked questions** — ranked list with counts
- Auto-refresh every 30 seconds
- Live status indicator

### 🔒 Security
- Rate limiting (configurable per minute)
- Input sanitization (XSS, SQL injection protection)
- Secure session handling with UUID-based session IDs
- Parameterized SQL queries (via SQLAlchemy)

## 📁 Project Structure

```
project/
├── app.py                      # Flask application entry point
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── chatbot/
│   ├── __init__.py
│   ├── intents.json            # FAQ training dataset
│   ├── preprocessing.py        # NLTK tokenization, lemmatization, cleaning
│   ├── response_engine.py      # Intent matching, similarity, context engine
│   └── model.py                # Chatbot model entry point
├── database/
│   ├── __init__.py
│   └── database.py             # SQLAlchemy models, CRUD, analytics queries
├── static/
│   ├── style.css               # Futuristic dark-mode theme
│   └── script.js               # Frontend interactions & API calls
└── templates/
    ├── index.html              # Main chatbot interface
    └── admin.html              # Admin analytics dashboard
```

## 🚀 Quick Start

### 1. Clone & Enter Directory
```bash
cd ai-assist-chatbot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Download NLTK Data (first run only)
The app will automatically download required NLTK data on first launch.

### 4. Run the Application
```bash
python app.py
```

The chatbot will be available at **http://localhost:5000**

### 5. Open Admin Dashboard
Navigate to **http://localhost:5000/admin** for analytics.

## 📡 API Reference

### `POST /api/chat`
Send a message to the chatbot.
```json
// Request
{ "message": "What are your timings?" }

// Response
{
  "response": "We are available from 9:00 AM to 6:00 PM, Monday through Friday. 🕘",
  "intent": "business_hours",
  "confidence": 0.87,
  "context": "hours"
}
```

### `GET /api/history`
Fetch chat history for the current session.
```json
{
  "history": [
    {
      "role": "user",
      "content": "Hello",
      "intent": null,
      "confidence": null,
      "timestamp": "2024-01-15T10:30:00+00:00"
    }
  ]
}
```

### `DELETE /api/clear-history`
Clear all messages in the current session.
```json
{ "success": true, "deleted": 12 }
```

### `GET /api/admin/stats`
Analytics data for the dashboard.
```json
{
  "total_users": 5,
  "total_messages": 42,
  "most_asked": [["What are your timings?", 3], ...],
  "activity": [{"date": "2024-01-15", "count": 10}, ...]
}
```

### `GET /api/health`
Health check endpoint.

## 🧠 NLP Details

The chatbot uses a **hybrid approach**:

1. **Primary:** `sentence-transformers` (all-MiniLM-L6-v2) for semantic embeddings  
2. **Fallback:** TF-IDF vectorization + cosine similarity via scikit-learn  
3. **Preprocessing:** NLTK tokenization, stopword removal, WordNet lemmatization  

### Confidence Thresholds
- **≥ 0.65** — High confidence: direct response
- **≥ 0.45** — Medium confidence: "I think..." prefix
- **< 0.45** — Low confidence: ask for rephrasing

### Context Tracking
The engine tracks the last 6 exchanges. Intents with `context_set` establish a context, and intents with `context_filter` only trigger when the matching context is active. This enables natural follow-ups like "And on Sunday?" after discussing business hours.

## 🛠️ Deployment

### Render / Railway
1. Push to GitHub
2. Create new Web Service
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app`
5. Add environment variables from `.env`

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | auto-generated | Flask secret key |
| `DATABASE_URL` | `sqlite:///database.db` | Database URI |
| `FLASK_ENV` | `development` | Environment mode |
| `MAX_CHAT_HISTORY` | `100` | Max history per session |
| `RATE_LIMIT_PER_MINUTE` | `30` | API rate limit |
| `PORT` | `5000` | Server port |

## 📦 Dependencies

- Flask 3.x — Web framework
- Flask-SQLAlchemy — ORM
- Flask-Limiter — Rate limiting
- Flask-CORS — Cross-origin support
- NLTK — Natural Language Toolkit
- scikit-learn — TF-IDF similarity (fallback)
- numpy — Numerical operations
- python-dotenv — Environment management
- gunicorn — Production server

> **Optional:** Uncomment `sentence-transformers` in `requirements.txt` for better NLP accuracy. Requires PyTorch.

## 📄 License

MIT — free to use, modify, and distribute.
