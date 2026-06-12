"""
app.py - AI-Powered Chatbot Web Application
Flask backend with SQLite, NLP chatbot engine, REST APIs, and admin dashboard.

Run with: python app.py
"""

import html
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())

# Configuration
app.config["MAX_CHAT_HISTORY"] = int(os.getenv("MAX_CHAT_HISTORY", "100"))
app.config["RATE_LIMIT_PER_MINUTE"] = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///database.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = 86400  # 24 hours

# Extensions
CORS(app, supports_credentials=True)

# Rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[f"{app.config['RATE_LIMIT_PER_MINUTE']}/minute"],
    storage_uri="memory://",
)

# Database (import & init after app creation to avoid circular import)
from database.database import (
    init_db,
    get_or_create_user,
    get_or_create_session,
    save_message,
    save_log,
    get_chat_history,
    clear_chat_history,
    get_total_users,
    get_total_messages,
    get_most_asked_questions,
    get_chat_activity,
)

init_db(app)

# Chatbot engine (import after app creation)
from chatbot.model import chat, reset_chat

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

# Patterns for input sanitisation — allow only safe characters
_SAFE_INPUT_RE = re.compile(r"[<>&\"'\\]")


def sanitise_input(text: str) -> str:
    """
    Sanitise user input to prevent XSS and injection attacks.
    - Strips HTML tags
    - Escapes special characters
    - Trims whitespace
    - Enforces max length
    """
    # Strip to reasonable length (prevent resource exhaustion)
    text = text[:1000]

    # Remove null bytes
    text = text.replace("\x00", "")

    # Escape HTML entities
    text = html.escape(text, quote=True)

    # Remove any remaining dangerous patterns
    text = _SAFE_INPUT_RE.sub("", text)

    return text.strip()


def get_session_id() -> str:
    """Get or create a persistent session ID for the current user."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.permanent = True
    return session["session_id"]


# ---------------------------------------------------------------------------
# Routes - Frontend pages
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve the main chatbot interface."""
    return render_template("index.html")


@app.route("/admin")
def admin_dashboard():
    """Serve the admin analytics dashboard."""
    return render_template("admin.html")


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@app.route("/api/chat", methods=["POST"])
@limiter.limit(lambda: f"{app.config['RATE_LIMIT_PER_MINUTE']}/minute")
def api_chat():
    """
    POST /api/chat
    Send a message to the chatbot and receive a response.

    Request body JSON: { "message": "Hello!" }
    Response JSON:     { "response": "...", "intent": "...", "confidence": 0.95, "context": "..." }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    # Sanitise input
    user_message = sanitise_input(user_message)
    if not user_message:
        return jsonify({"error": "Invalid message content"}), 400

    try:
        # Get chatbot response
        result = chat(user_message)

        # Database persistence
        sid = get_session_id()
        user = get_or_create_user(sid, request.remote_addr, request.user_agent.string if request.user_agent else None)
        chat_session = get_or_create_session(user.id)

        save_message(chat_session.id, "user", user_message)
        save_message(
            chat_session.id,
            "bot",
            result["response"],
            intent=result.get("intent"),
            confidence=result.get("confidence"),
        )
        save_log("chat", chat_session.id, f"intent={result.get('intent')}, confidence={result.get('confidence')}")

        return jsonify(result)

    except Exception as exc:
        logger.exception("Chat API error")
        save_log("error", details=str(exc))
        return jsonify({"response": "Sorry, an error occurred. Please try again later.", "intent": "error", "confidence": 0.0, "context": None}), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    """
    GET /api/history
    Fetch chat history for the current session.

    Response JSON: { "history": [ { "role": "user", "content": "...", ... }, ... ] }
    """
    try:
        sid = get_session_id()
        user = get_or_create_user(sid)
        chat_session = get_or_create_session(user.id)
        messages = get_chat_history(chat_session.id)
        return jsonify({
            "history": [msg.to_dict() for msg in messages],
        })
    except Exception as exc:
        logger.exception("History API error")
        return jsonify({"error": "Failed to fetch history"}), 500


@app.route("/api/clear-history", methods=["DELETE"])
def api_clear_history():
    """
    DELETE /api/clear-history
    Clear all chat messages in the current session.

    Response JSON: { "success": true, "deleted": N }
    """
    try:
        sid = get_session_id()
        user = get_or_create_user(sid)
        chat_session = get_or_create_session(user.id)
        deleted = clear_chat_history(chat_session.id)
        reset_chat()  # Also reset conversation memory
        save_log("reset", chat_session.id, f"cleared {deleted} messages")
        return jsonify({"success": True, "deleted": deleted})
    except Exception as exc:
        logger.exception("Clear history API error")
        return jsonify({"error": "Failed to clear history"}), 500


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.route("/api/health")
def api_health():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


# ---------------------------------------------------------------------------
# Admin API - Analytics
# ---------------------------------------------------------------------------


@app.route("/api/admin/stats", methods=["GET"])
@limiter.limit("10/minute")
def api_admin_stats():
    """
    GET /api/admin/stats
    Return aggregate analytics data for the admin dashboard.
    """
    try:
        stats = {
            "total_users": get_total_users(),
            "total_messages": get_total_messages(),
            "most_asked": get_most_asked_questions(10),
            "activity": get_chat_activity(7),
        }
        return jsonify(stats)
    except Exception as exc:
        logger.exception("Admin stats API error")
        return jsonify({"error": "Failed to load stats"}), 500


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.errorhandler(429)
def ratelimit_handler(_exc):
    """Handle rate limit exceeded."""
    return jsonify({
        "error": "Rate limit exceeded. Please slow down.",
        "response": "You're sending messages too quickly! Please wait a moment.",
        "intent": "rate_limit",
        "confidence": 0.0,
        "context": None,
    }), 429


@app.errorhandler(404)
def not_found(_exc):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(_exc):
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    logger.info("Starting AI Chatbot on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
