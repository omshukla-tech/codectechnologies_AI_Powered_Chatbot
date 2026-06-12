"""
response_engine.py - Chatbot Response Engine

Handles intent recognition, semantic similarity matching,
confidence scoring, and contextual conversation management.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from chatbot.preprocessing import preprocess, get_processed_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _intents_path() -> str:
    return os.path.join(os.path.dirname(__file__), "intents.json")


# ---------------------------------------------------------------------------
# Intent loader
# ---------------------------------------------------------------------------

class IntentManager:
    """Loads and provides access to intents from the JSON dataset."""

    def __init__(self, intents_file: Optional[str] = None):
        self.intents_file = intents_file or _intents_path()
        self._intents: List[Dict] = []
        self._patterns: List[Tuple[str, str, str]] = []  # (tag, pattern_text, context_set or None)
        self.load()

    def load(self) -> None:
        """Load intents from JSON file."""
        try:
            with open(self.intents_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._intents = data.get("intents", [])
            self._rebuild_pattern_index()
            logger.info("Loaded %d intents with %d patterns", len(self._intents), len(self._patterns))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.error("Failed to load intents: %s", exc)
            self._intents = []
            self._patterns = []

    def _rebuild_pattern_index(self) -> None:
        """Rebuild the flat pattern list with tags and context."""
        self._patterns = []
        for intent in self._intents:
            tag = intent.get("tag", "unknown")
            context_set = intent.get("context_set")
            for pattern in intent.get("patterns", []):
                if pattern.strip():
                    self._patterns.append((tag, pattern.strip().lower(), context_set))

    def get_intent(self, tag: str) -> Optional[Dict]:
        """Get an intent dict by its tag."""
        for intent in self._intents:
            if intent["tag"] == tag:
                return intent
        return None

    def get_all_patterns(self) -> List[Tuple[str, str, Optional[str]]]:
        """Return all (tag, pattern, context_set) tuples."""
        return list(self._patterns)

    @property
    def intents(self) -> List[Dict]:
        return self._intents


# ---------------------------------------------------------------------------
# Embedding / similarity backend
# ---------------------------------------------------------------------------

class SimilarityEngine:
    """
    Provides cosine-similarity based matching.

    Tries to use sentence-transformers first; falls back to
    TF-IDF + cosine similarity via scikit-learn.
    """

    def __init__(self):
        self._model = None
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None
        self._use_transformers: Optional[bool] = None
        self._loaded = False

    def _try_load_transformers(self) -> bool:
        """Attempt to load sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model 'all-MiniLM-L6-v2'")
            return True
        except ImportError:
            logger.info("sentence-transformers not available; using TF-IDF fallback")
            return False
        except Exception as exc:
            logger.warning("Failed to load sentence-transformers: %s; using TF-IDF", exc)
            return False

    def _ensure_loaded(self) -> None:
        """One-time lazy initialisation."""
        if self._loaded:
            return
        self._loaded = True
        self._use_transformers = self._try_load_transformers()

    def _prepare_tfidf(self, texts: List[str]) -> None:
        """Build TF-IDF matrix for the given texts."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        self._tfidf_vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=5000,
        )
        self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(texts)

    def compute_similarities(self, query: str, candidates: List[str]) -> List[float]:
        """
        Return a list of cosine similarity scores between `query` and each
        candidate string in `candidates`.
        """
        self._ensure_loaded()

        if not candidates:
            return []

        if self._use_transformers and self._model is not None:
            # sentence-transformers
            query_emb = self._model.encode([query])
            cand_emb = self._model.encode(candidates)
            from sklearn.metrics.pairwise import cosine_similarity
            scores = cosine_similarity(query_emb, cand_emb)[0]
            return [float(s) for s in scores]

        # TF-IDF fallback
        all_texts = [query] + candidates
        self._prepare_tfidf(all_texts)
        if self._tfidf_matrix is None:
            return [0.0] * len(candidates)
        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(self._tfidf_matrix[0:1], self._tfidf_matrix[1:])[0]
        return [float(s) for s in scores]


# ---------------------------------------------------------------------------
# Conversation context
# ---------------------------------------------------------------------------

class ConversationMemory:
    """
    Maintains short-term conversation context (last N exchanges).
    Used to resolve follow-up questions (e.g., "And on Sunday?")
    """

    def __init__(self, max_exchanges: int = 6):
        self.max_exchanges = max_exchanges
        self.history: List[Dict] = []
        self.current_context: Optional[str] = None

    def add_exchange(self, user_message: str, bot_response: str, intent_tag: str, context: Optional[str] = None) -> None:
        """Record one user ↔ bot exchange."""
        self.history.append({
            "user": user_message,
            "bot": bot_response,
            "intent": intent_tag,
            "context_set": context,
        })
        if context:
            self.current_context = context
        # Keep only the last N
        if len(self.history) > self.max_exchanges:
            self.history.pop(0)

    def get_last_intent(self) -> Optional[str]:
        """Return the intent tag of the most recent exchange."""
        if self.history:
            return self.history[-1].get("intent")
        return None

    def get_last_context(self) -> Optional[str]:
        """Return the last context_set value."""
        return self.current_context

    def get_recent_messages(self, n: int = 3) -> List[str]:
        """Return the last N user messages for additional context."""
        return [h["user"] for h in self.history[-n:]]

    def clear(self) -> None:
        """Reset conversation memory."""
        self.history.clear()
        self.current_context = None


# ---------------------------------------------------------------------------
# Response Engine (orchestrator)
# ---------------------------------------------------------------------------

class ResponseEngine:
    """
    Main response engine combining intent matching, similarity scoring,
    context management, and response selection.
    """

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.65
    MEDIUM_CONFIDENCE = 0.45

    def __init__(self):
        self.intent_manager = IntentManager()
        self.similarity = SimilarityEngine()
        self.memory = ConversationMemory()
        self._response_idx: Dict[str, int] = {}

        # Pre-process all pattern texts
        self._pattern_texts: List[str] = []
        self._pattern_meta: List[Tuple[str, Optional[str]]] = []  # (tag, context_set)
        self._rebuild_pattern_cache()

    def _rebuild_pattern_cache(self) -> None:
        """Build pre-processed pattern cache for similarity matching."""
        self._pattern_texts.clear()
        self._pattern_meta.clear()
        for tag, pattern, ctx in self.intent_manager.get_all_patterns():
            self._pattern_texts.append(get_processed_text(pattern))
            self._pattern_meta.append((tag, ctx))

    def _matches_context(self, intent_tag: str) -> bool:
        """
        Check if the intent requires a specific context filter.
        If it does, it only matches when that context is active.
        """
        intent = self.intent_manager.get_intent(intent_tag)
        if intent is None:
            return True
        context_filter = intent.get("context_filter")
        if context_filter is None:
            return True  # No filter = always valid
        return self.memory.get_last_context() == context_filter

    def _get_best_match(self, user_message: str) -> Tuple[str, float]:
        """
        Find the best-matching intent tag and confidence score
        for the given user message.
        """
        processed = get_processed_text(user_message)

        if not self._pattern_texts:
            return "unknown", 0.0

        # Compute similarities
        scores = self.similarity.compute_similarities(processed, self._pattern_texts)

        if not scores:
            return "unknown", 0.0

        # Find best score
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        best_score = scores[best_idx]
        best_tag, _ = self._pattern_meta[best_idx]

        # If score is below threshold, try checking if a context-dependent
        # intent matches reasonably well
        if best_score < self.MEDIUM_CONFIDENCE:
            # Check context-filtered intents with a lower bar
            for i, (tag, _) in enumerate(self._pattern_meta):
                if self._matches_context(tag) and scores[i] >= self.MEDIUM_CONFIDENCE:
                    return tag, scores[i]

        return best_tag, best_score

    def _select_response(self, tag: str) -> str:
        """Pick a response from the matched intent."""
        intent = self.intent_manager.get_intent(tag)
        if intent is None:
            return "I'm not sure about that. Could you rephrase your question?"
        responses = intent.get("responses", [])
        if not responses:
            return "I don't have an answer for that right now."
        # Simple round-robin selection for variety
        idx = self._response_idx.get(tag, 0) % len(responses)
        self._response_idx[tag] = idx + 1
        return responses[idx]

    def get_response(self, user_message: str) -> Dict:
        """
        Process a user message and return a structured response.

        Returns:
        {
            "response": str,          # Bot reply text
            "intent": str,            # Matched intent tag
            "confidence": float,       # 0.0 – 1.0
            "context": str | None     # New context set (if any)
        }
        """
        # Clean input
        cleaned = user_message.strip()
        if not cleaned:
            return {
                "response": "Please say something! I'm here to help. 😊",
                "intent": "empty",
                "confidence": 1.0,
                "context": None,
            }

        # Get best match
        best_tag, confidence = self._get_best_match(cleaned)

        # Build response based on confidence
        if confidence >= self.HIGH_CONFIDENCE:
            response = self._select_response(best_tag)
        elif confidence >= self.MEDIUM_CONFIDENCE:
            base = self._select_response(best_tag)
            response = f"I think {base[0].lower()}{base[1:]}"
        else:
            best_tag = "unknown"
            intent = self.intent_manager.get_intent("unknown")
            responses = intent["responses"] if intent else ["Could you rephrase that?"]
            response = responses[0]

        # Check context for matched intent
        intent_obj = self.intent_manager.get_intent(best_tag)
        new_context = intent_obj.get("context_set") if intent_obj else None

        # Record in memory
        self.memory.add_exchange(cleaned, response, best_tag, new_context)

        return {
            "response": response,
            "intent": best_tag,
            "confidence": round(confidence, 3),
            "context": new_context,
        }

    def reset_conversation(self) -> None:
        """Clear conversation memory."""
        self.memory.clear()
        self._response_idx.clear()
