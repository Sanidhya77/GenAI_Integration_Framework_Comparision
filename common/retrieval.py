"""
Document store retrieval logic for the pipeline endpoint (Endpoint 3).

Implements keyword-based search over genai_concepts.txt and returns
the most relevant passage. Provides both synchronous and asynchronous
versions with a controlled 50ms delay simulating vector DB latency.

Both versions use IDENTICAL search logic — the only difference is
the sleep mechanism (time.sleep vs asyncio.sleep).
"""

import asyncio
import time

from common.config import DOCUMENT_STORE_PATH, RETRIEVAL_DELAY_SECONDS


def _load_paragraphs():
    """Load and split the document store into paragraphs.

    Returns a list of non-empty paragraph strings.
    """
    with open(DOCUMENT_STORE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on double newlines to get paragraphs
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    return paragraphs


def _score_paragraph(paragraph, keywords):
    """Score a paragraph by counting keyword occurrences (case-insensitive).

    This is intentionally simple — the thesis tests framework behaviour,
    not retrieval algorithm quality.
    """
    paragraph_lower = paragraph.lower()
    score = 0
    for keyword in keywords:
        score += paragraph_lower.count(keyword.lower())
    return score


def _extract_keywords(query):
    """Extract meaningful keywords from the user query.

    Removes common stop words and returns lowercase keyword list.
    """
    stop_words = {
        "what", "is", "how", "are", "the", "a", "an", "in", "of", "and",
        "to", "for", "it", "that", "this", "with", "on", "as", "by", "at",
        "from", "or", "be", "do", "does", "used", "can", "its", "into",
    }
    words = query.lower().split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    return keywords


def _search(query):
    """Core search logic — shared by sync and async versions.

    Returns the most relevant paragraph based on keyword overlap.
    """
    paragraphs = _load_paragraphs()
    keywords = _extract_keywords(query)

    if not keywords or not paragraphs:
        # Fallback: return the first paragraph
        return paragraphs[0] if paragraphs else ""

    scored = [(p, _score_paragraph(p, keywords)) for p in paragraphs]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return the highest-scoring paragraph
    return scored[0][0]


def retrieve_context_sync(query):
    """Synchronous retrieval with controlled delay.

    Used by Flask and Django (sync frameworks).
    Stage 2 of the pipeline: search + 50ms simulated vector DB latency.
    """
    context = _search(query)
    time.sleep(RETRIEVAL_DELAY_SECONDS)  # Simulated vector DB latency
    return context


async def retrieve_context_async(query):
    """Asynchronous retrieval with controlled delay.

    Used by FastAPI and Tornado (async frameworks).
    Stage 2 of the pipeline: search + 50ms simulated vector DB latency.
    """
    context = _search(query)
    await asyncio.sleep(RETRIEVAL_DELAY_SECONDS)  # Simulated vector DB latency
    return context