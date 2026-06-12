"""
model.py - Chatbot Model Entry Point

Provides a simple interface to the chatbot engine for the Flask app.
"""

import logging
from typing import Dict

from chatbot.response_engine import ResponseEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton chatbot engine
# ---------------------------------------------------------------------------
_engine: ResponseEngine = None  # type: ignore[assignment]


def get_engine() -> ResponseEngine:
    """Get or create the singleton ResponseEngine instance."""
    global _engine
    if _engine is None:
        _engine = ResponseEngine()
        logger.info("Chatbot engine initialized")
    return _engine


def chat(user_message: str) -> Dict:
    """
    Send a user message to the chatbot and get a response.

    Args:
        user_message: The raw text from the user.

    Returns:
        dict with keys: response, intent, confidence, context
    """
    engine = get_engine()
    return engine.get_response(user_message)


def reset_chat() -> Dict:
    """
    Reset the current conversation context.
    Returns a confirmation message.
    """
    engine = get_engine()
    engine.reset_conversation()
    return {
        "response": "Conversation has been reset. Let's start fresh! 👋",
        "intent": "reset",
        "confidence": 1.0,
        "context": None,
    }
