"""
gemini_helpers.py
Shared wrappers for Google Gemini APIs used in Indic NLP comparison cells.

Authentication: set GEMINI_API_KEY in .env
Gracefully skips if API key is missing (returns None / prints warning).
"""

import os
import logging
import time
import threading
from functools import wraps
from typing import Optional

import numpy as np
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Rate limiter (shared with sarvam_helpers pattern) ────────────────────────

class RateLimiter:
    """Token-bucket rate limiter (thread-safe)."""

    def __init__(self, max_calls: int = 60, period: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            self._calls = [t for t in self._calls if now - t < self.period]
            if len(self._calls) >= self.max_calls:
                sleep_time = self.period - (now - self._calls[0])
                logger.info("Gemini rate limit: sleeping %.1fs", sleep_time)
                time.sleep(max(sleep_time, 0))
                self._calls = [t for t in self._calls if time.time() - t < self.period]
            self._calls.append(time.time())


_rate_limiter = RateLimiter()


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator: exponential backoff on rate-limit (429) errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    msg = str(exc).lower()
                    is_rate = "429" in msg or "rate limit" in msg or "too many" in msg
                    if is_rate and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning("Gemini 429 – retrying in %.1fs (attempt %d/%d)",
                                       delay, attempt + 1, max_retries)
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator


# ── Client factory ───────────────────────────────────────────────────────────

GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"
GEMINI_EMBED_MODEL = "models/text-embedding-004"


def load_gemini_client(model: str = GEMINI_DEFAULT_MODEL):
    """Return a google.generativeai GenerativeModel instance.

    Args:
        model: Gemini model name (default: gemini-2.0-flash).

    Returns:
        GenerativeModel instance, or None if API key is missing.
    """
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key in ("", "your_gemini_key_here"):
        logger.warning(
            "GEMINI_API_KEY not set — Gemini comparison cells will be skipped. "
            "Add it to .env: GEMINI_API_KEY=<your_key>"
        )
        return None
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "google-generativeai not installed. Run: pip install google-generativeai"
        ) from exc
    genai.configure(api_key=api_key)
    logger.info("Gemini client initialised (model=%s)", model)
    return genai.GenerativeModel(model)


# ── API wrappers ─────────────────────────────────────────────────────────────

@retry_with_backoff()
def gemini_chat(
    model,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> Optional[str]:
    """Chat completion via Google Gemini.

    Args:
        model: GenerativeModel instance (from load_gemini_client).
        messages: List of {role, content} dicts (OpenAI-style).
        temperature: Sampling temperature.
        max_tokens: Max output tokens.

    Returns:
        Assistant response string, or None if model is None.
    """
    if model is None:
        logger.warning("Gemini model is None — skipping chat call.")
        return None
    _rate_limiter.acquire()

    import google.generativeai as genai

    # Convert OpenAI-style messages to Gemini format
    gemini_contents = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            # Prepend system message as user context
            gemini_contents.append({"role": "user", "parts": [msg["content"]]})
            gemini_contents.append({"role": "model", "parts": ["Understood."]})
        elif role == "user":
            gemini_contents.append({"role": "user", "parts": [msg["content"]]})
        elif role == "assistant":
            gemini_contents.append({"role": "model", "parts": [msg["content"]]})

    response = model.generate_content(
        gemini_contents,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text


@retry_with_backoff()
def gemini_embed(
    texts: list[str],
    model: str = GEMINI_EMBED_MODEL,
) -> Optional[np.ndarray]:
    """Get embeddings from Google's text-embedding-004 model.

    Args:
        texts: List of strings to embed.
        model: Embedding model name.

    Returns:
        numpy array of shape (len(texts), embedding_dim), or None if API key missing.
    """
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key in ("", "your_gemini_key_here"):
        logger.warning("GEMINI_API_KEY not set — skipping embedding call.")
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai not installed — skipping embedding call.")
        return None
    genai.configure(api_key=api_key)

    _rate_limiter.acquire()
    result = genai.embed_content(model=model, content=texts)
    return np.array(result["embedding"]) if isinstance(texts, str) else np.array(result["embedding"])


# ── Language helpers ─────────────────────────────────────────────────────────

SARVAM_LANG_NAMES = {
    "hi-IN": "Hindi", "ta-IN": "Tamil", "bn-IN": "Bengali",
    "te-IN": "Telugu", "kn-IN": "Kannada", "ml-IN": "Malayalam",
    "mr-IN": "Marathi", "gu-IN": "Gujarati", "pa-IN": "Punjabi",
    "mni-IN": "Meitei", "kok-IN": "Konkani", "en-IN": "English",
}

GEMINI_MODELS = {
    "flagship": "gemini-2.0-flash",
    "embed": "models/text-embedding-004",
}


# ── Comparison helpers ───────────────────────────────────────────────────────

def compare_chat_responses(
    sarvam_client,
    gemini_model,
    messages: list[dict],
    sarvam_fn,
    label: str = "Task",
) -> dict[str, Optional[str]]:
    """Run the same prompt through Sarvam-M and Gemini-2.0-flash.

    Args:
        sarvam_client: Authenticated SarvamAI client.
        gemini_model: Gemini GenerativeModel (from load_gemini_client).
        messages: Prompt messages.
        sarvam_fn: Callable — typically sarvam_helpers.chat_complete.
        label: Label printed in output.

    Returns:
        Dict with keys 'sarvam' and 'gemini'.
    """
    results: dict[str, Optional[str]] = {}

    print(f"\n[{label}] Running Sarvam-M...")
    try:
        r = sarvam_fn(sarvam_client, messages, reasoning_effort="low")
        if "<think>" in r:
            r = r.split("</think>")[-1].strip()
        results["sarvam"] = r
        print(f"  Sarvam-M: {r[:200]}")
    except Exception as e:
        results["sarvam"] = f"[Error: {e}]"
        print(f"  Sarvam-M Error: {e}")

    print(f"[{label}] Running Gemini-2.0-flash...")
    try:
        r = gemini_chat(gemini_model, messages, temperature=0.3)
        results["gemini"] = r
        print(f"  Gemini: {(r or 'N/A')[:200]}")
    except Exception as e:
        results["gemini"] = f"[Error: {e}]"
        print(f"  Gemini Error: {e}")

    return results
