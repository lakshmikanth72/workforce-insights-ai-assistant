"""Small TF-IDF retriever for the local HR knowledge document."""

from pathlib import Path
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_PATH = Path(__file__).with_name("knowledge.txt")


def _load_chunks() -> List[str]:
    if not KNOWLEDGE_PATH.exists():
        return []
    text = KNOWLEDGE_PATH.read_text(encoding="utf-8").strip()
    if not text:
        return []
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    return paragraphs or [text]


def retrieve_context(question: str, top_k: int = 3) -> str:
    """Return the most relevant knowledge chunks, or an empty string."""
    chunks = _load_chunks()
    if not chunks or not question.strip():
        return ""

    try:
        vectors = TfidfVectorizer(stop_words="english").fit_transform(chunks + [question])
        scores = cosine_similarity(vectors[-1], vectors[:-1]).ravel()
    except ValueError:
        return ""

    ranked = scores.argsort()[::-1]
    selected = [chunks[index] for index in ranked[:top_k] if scores[index] > 0]
    return "\n\n".join(selected)
