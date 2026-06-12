"""
preprocessing.py - NLP Text Preprocessing Module

Handles tokenization, lemmatization, stopword removal, and text cleaning
for natural language understanding.
"""

import re
import html
import unicodedata
from typing import List, Optional

# ---------------------------------------------------------------------------
# Lazy NLTK data download (runs once)
# ---------------------------------------------------------------------------
def _ensure_nltk_data() -> None:
    """Download required NLTK data packages if not already present."""
    import nltk
    import ssl

    try:
        _create_unverified_https_context = ssl._create_unverified_context  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context  # type: ignore[attr-defined]

    for resource in ("tokenizers/punkt", "corpora/stopwords", "corpora/wordnet"):
        try:
            nltk.data.find(resource)
        except LookupError:
            nltk.download(resource.split("/")[1], quiet=True)


_ensure_nltk_data()

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# ---------------------------------------------------------------------------
# Lazy-loaded singletons
# ---------------------------------------------------------------------------
_lemmatizer: Optional[WordNetLemmatizer] = None
_stop_words: Optional[set] = None


def _get_lemmatizer() -> WordNetLemmatizer:
    global _lemmatizer
    if _lemmatizer is None:
        _lemmatizer = WordNetLemmatizer()
    return _lemmatizer


def _get_stop_words() -> set:
    global _stop_words
    if _stop_words is None:
        _stop_words = set(stopwords.words("english"))
    return _stop_words


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Clean and normalize input text:
    - Decode HTML entities
    - Remove URLs, emails, and special characters
    - Normalize Unicode (NFKC)
    - Remove extra whitespace
    """
    # HTML entity decode
    text = html.unescape(text)

    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # Remove email addresses
    text = re.sub(r"\S+@\S+", "", text)

    # Remove special characters but keep basic punctuation and alphabets
    text = re.sub(r"[^a-zA-Z0-9\s?.!,'-]", "", text)

    # Normalize unicode (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize(text: str) -> List[str]:
    """Tokenize text into word tokens using NLTK."""
    return nltk.word_tokenize(text.lower())


def remove_stopwords(tokens: List[str]) -> List[str]:
    """Remove English stopwords from token list."""
    stops = _get_stop_words()
    return [t for t in tokens if t not in stops]


def lemmatize(tokens: List[str]) -> List[str]:
    """Lemmatize tokens to their base forms."""
    lemmatizer = _get_lemmatizer()
    return [lemmatizer.lemmatize(t) for t in tokens]


def preprocess(text: str) -> List[str]:
    """
    Full preprocessing pipeline:
    1. Clean text
    2. Tokenize
    3. Remove stopwords
    4. Lemmatize

    Returns a list of processed tokens.
    """
    cleaned = clean_text(text)
    tokens = tokenize(cleaned)
    tokens_no_stop = remove_stopwords(tokens)
    lemmatized = lemmatize(tokens_no_stop)
    return lemmatized


def get_processed_text(text: str) -> str:
    """Return preprocessed text as a single space-joined string."""
    return " ".join(preprocess(text))
