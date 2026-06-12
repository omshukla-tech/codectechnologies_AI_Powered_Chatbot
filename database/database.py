"""
database.py - SQLite Database Layer

Provides ORM-based database tables and CRUD operations for
users, chat sessions, messages, and activity logs.
Uses Flask-SQLAlchemy for production-quality database management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text

logger = logging.getLogger(__name__)

db = SQLAlchemy()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(db.Model):  # type: ignore[name-defined]
    """Represents a unique chat user (tracked by session)."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    sessions = db.relationship("ChatSession", backref="user", lazy="dynamic")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "message_count": self.sessions.count(),
        }


class ChatSession(db.Model):  # type: ignore[name-defined]
    """A single chat session belonging to a user."""
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    messages = db.relationship("Message", backref="session", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "session_uuid": self.session_uuid,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "message_count": self.messages.count(),
        }


class Message(db.Model):  # type: ignore[name-defined]
    """A single chat message (user or bot)."""
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    role = db.Column(db.String(16), nullable=False)  # "user" | "bot"
    content = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(64), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "confidence": self.confidence,
            "timestamp": self.created_at.isoformat() if self.created_at else None,
        }


class Log(db.Model):  # type: ignore[name-defined]
    """Activity log for admin analytics."""
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(64), nullable=False)  # "chat", "reset", "error", "visit"
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db(app) -> None:
    """Initialise the database with the Flask app."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        logger.info("Database tables created / verified")


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def get_or_create_user(session_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> User:
    """Find existing user by session_id or create a new one."""
    user = User.query.filter_by(session_id=session_id).first()
    if user is None:
        user = User(
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(user)
        db.session.commit()
        logger.info("Created new user with session_id=%s", session_id)
    else:
        # Update last active
        user.last_active = datetime.now(timezone.utc)
        db.session.commit()
    return user


def get_or_create_session(user_id: int) -> ChatSession:
    """Get the active session for a user, or create a new one."""
    session = ChatSession.query.filter_by(user_id=user_id, is_active=True).first()
    if session is None:
        session = ChatSession(user_id=user_id)
        db.session.add(session)
        db.session.commit()
    return session


def save_message(
    session_id: int,
    role: str,
    content: str,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Message:
    """Persist a chat message."""
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        intent=intent,
        confidence=confidence,
    )
    db.session.add(msg)
    db.session.commit()
    return msg


def save_log(
    event_type: str,
    session_id: Optional[int] = None,
    details: Optional[str] = None,
) -> Log:
    """Persist an activity log entry."""
    log = Log(event_type=event_type, session_id=session_id, details=details)
    db.session.add(log)
    db.session.commit()
    return log


def get_chat_history(session_id: int, limit: int = 100) -> List[Message]:
    """Retrieve messages for a session in chronological order."""
    return (
        Message.query
        .filter_by(session_id=session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )


def clear_chat_history(session_id: int) -> int:
    """Delete all messages for a session. Returns count of deleted messages."""
    count = Message.query.filter_by(session_id=session_id).delete()
    db.session.commit()
    return count


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------

def get_total_users() -> int:
    """Return the total number of registered users."""
    return User.query.count()


def get_total_messages() -> int:
    """Return the total number of messages across all sessions."""
    return Message.query.count()


def get_most_asked_questions(limit: int = 10) -> List[Tuple[str, int]]:
    """
    Return the most frequently asked questions (user messages)
    as a list of (content, count) sorted by count descending.
    """
    results = (
        db.session.query(Message.content, func.count(Message.id).label("cnt"))
        .filter(Message.role == "user")
        .group_by(Message.content)
        .order_by(text("cnt DESC"))
        .limit(limit)
        .all()
    )
    return [(r[0], r[1]) for r in results]


def get_chat_activity(days: int = 7) -> List[Dict]:
    """
    Return daily message counts for the last N days.
    Used by the analytics dashboard for the activity graph.
    """
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.session.query(
            func.date(Message.created_at).label("day"),
            func.count(Message.id).label("count"),
        )
        .filter(Message.created_at >= since)
        .group_by(text("day"))
        .order_by(text("day ASC"))
        .all()
    )

    return [{"date": r[0], "count": r[1]} for r in results]
