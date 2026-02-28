"""
krutrim_helpers.py
Shared wrappers for Krutrim Cloud APIs used in Indic NLP comparison cells.

Krutrim Cloud is OpenAI-compatible at https://cloud.olakrutrim.com/v1
All chat/embedding calls use the openai Python client pointed at that base URL.
KrutrimTranslate uses the native krutrim-cloud SDK.

Authentication: set KRUTRIM_CLOUD_API_KEY in .env
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
                logger.info("Krutrim rate limit: sleeping %.1fs", sleep_time)
                time.sleep(max(sleep_time, 0))
                self._calls = [t for t in self._calls if time.time() - t < self.period]
            self._calls.append(time.time())


_rate_limiter = RateLimiter()


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    msg = str(exc).lower()
                    is_rate = "429" in msg or "rate limit" in msg
                    if is_rate and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning("Krutrim 429 – retrying in %.1fs", delay)
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator


# ── Client factory ────────────────────────────────────────────────────────────

KRUTRIM_BASE_URL = "https://cloud.olakrutrim.com/v1"
KRUTRIM_DEFAULT_MODEL = "Krutrim-spectre-v2"
KRUTRIM_EMBED_MODEL = "Bhasantarit-mini"


def load_openai_client():
    """Return an OpenAI client pointed at the Krutrim Cloud endpoint.

    Uses KRUTRIM_CLOUD_API_KEY from .env.
    All OpenAI-compatible APIs (chat, embeddings) use this client.
    """
    load_dotenv(override=True)
    api_key = os.getenv("KRUTRIM_CLOUD_API_KEY")
    if not api_key or api_key == "your_krutrim_key_here":
        raise EnvironmentError(
            "KRUTRIM_CLOUD_API_KEY not set. Add it to .env: "
            "KRUTRIM_CLOUD_API_KEY=<your_key>"
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("openai package not installed. Run: pip install openai") from exc
    logger.info("Krutrim OpenAI-compat client initialised (base=%s)", KRUTRIM_BASE_URL)
    return OpenAI(api_key=api_key, base_url=KRUTRIM_BASE_URL)


def load_krutrim_client():
    """Return native KrutrimCloud client (for KrutrimTranslate, Bhashik TTS etc.)."""
    load_dotenv(override=True)
    api_key = os.getenv("KRUTRIM_CLOUD_API_KEY")
    if not api_key or api_key == "your_krutrim_key_here":
        raise EnvironmentError("KRUTRIM_CLOUD_API_KEY not set in .env")
    try:
        from krutrim_cloud import KrutrimCloud
    except ImportError as exc:
        raise ImportError(
            "krutrim-cloud not installed. Run: pip install krutrim-cloud"
        ) from exc
    return KrutrimCloud(api_key=api_key)


# ── API wrappers ──────────────────────────────────────────────────────────────

@retry_with_backoff()
def krutrim_chat(
    client,
    messages: list[dict],
    model: str = KRUTRIM_DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    """Chat completion via Krutrim Cloud (OpenAI-compatible).

    Args:
        client: OpenAI client pointing at cloud.olakrutrim.com/v1.
        messages: List of {role, content} dicts.
        model: Krutrim-spectre-v2 (default) | Krutrim-LLM-2 | Meta-Llama-3-8B-Instruct.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.

    Returns:
        Assistant response string.
    """
    _rate_limiter.acquire()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


@retry_with_backoff()
def krutrim_translate(
    client,
    text: str,
    src: str = "en",
    tgt: str = "hi",
) -> str:
    """Translate using KrutrimTranslate via the native SDK.

    Supported language codes (ISO 639-1 short form, no region suffix):
        en, hi, bn, ta, te, kn, ml, mr, gu, pa

    Args:
        client: KrutrimCloud native client (from load_krutrim_client()).
        text: Source text.
        src: Source language short code (e.g. 'en', 'hi').
        tgt: Target language short code.

    Returns:
        Translated string, or raises on unsupported pair.
    """
    _rate_limiter.acquire()
    try:
        response = client.language_labs.translate(
            texts=[text],
            source_language=src,
            target_language=tgt,
        )
        # Response is a list of translated strings
        if isinstance(response, list):
            return response[0] if response else ""
        if hasattr(response, "translations"):
            return response.translations[0]
        return str(response)
    except Exception as exc:
        # KrutrimTranslate may not be available on all tiers; fall back gracefully
        raise RuntimeError(f"KrutrimTranslate error ({src}->{tgt}): {exc}") from exc


@retry_with_backoff()
def krutrim_embed(
    client,
    texts: list[str],
    model: str = KRUTRIM_EMBED_MODEL,
) -> np.ndarray:
    """Get embeddings from Krutrim's Bhasantarit-mini / Vyakyarth model.

    Args:
        client: OpenAI-compat client.
        texts: List of strings to embed.
        model: Bhasantarit-mini (default, 768-dim Indic embeddings).

    Returns:
        numpy array of shape (len(texts), embedding_dim).
    """
    _rate_limiter.acquire()
    response = client.embeddings.create(model=model, input=texts)
    return np.array([d.embedding for d in response.data])


# ── Language code mapping ─────────────────────────────────────────────────────
# Sarvam uses BCP-47 (e.g. 'hi-IN'); Krutrim uses ISO 639-1 short codes.
# Use this map to convert when comparing side-by-side.

SARVAM_TO_KRUTRIM_LANG = {
    "hi-IN": "hi",
    "ta-IN": "ta",
    "bn-IN": "bn",
    "te-IN": "te",
    "kn-IN": "kn",
    "ml-IN": "ml",
    "mr-IN": "mr",
    "gu-IN": "gu",
    "pa-IN": "pa",
    "en-IN": "en",
}

KRUTRIM_LANG_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "bn": "Bengali",
    "te": "Telugu", "kn": "Kannada", "ml": "Malayalam",
    "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "en": "English",
}

KRUTRIM_MODELS = {
    "flagship":  "Krutrim-spectre-v2",
    "efficient": "Krutrim-LLM-2",
    "llama":     "Meta-Llama-3-8B-Instruct",
    "embed":     "Bhasantarit-mini",
}


# ── Comparison helpers ────────────────────────────────────────────────────────

def compare_chat_responses(
    sarvam_client,
    krutrim_client,
    messages: list[dict],
    sarvam_fn,
    label: str = "Task",
) -> dict[str, str]:
    """Run the same prompt through Sarvam-M and Krutrim-spectre-v2.

    Args:
        sarvam_client: Authenticated SarvamAI client.
        krutrim_client: OpenAI-compat client for Krutrim.
        messages: Prompt messages.
        sarvam_fn: Callable — typically sarvam_helpers.chat_complete.
        label: Label printed in output.

    Returns:
        Dict with keys 'sarvam' and 'krutrim'.
    """
    results: dict[str, str] = {}
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

    print(f"[{label}] Running Krutrim-spectre-v2...")
    try:
        r = krutrim_chat(krutrim_client, messages)
        results["krutrim"] = r
        print(f"  Krutrim: {r[:200]}")
    except Exception as e:
        results["krutrim"] = f"[Error: {e}]"
        print(f"  Krutrim Error: {e}")

    return results


def compare_translations(
    sarvam_client,
    krutrim_native_client,
    krutrim_openai_client,
    text: str,
    src_sarvam: str,
    tgt_sarvam: str,
    sarvam_translate_fn,
    reference: Optional[str] = None,
) -> dict[str, str]:
    """Run translation through Sarvam Mayura v1, Sarvam-Translate v1,
    and Krutrim-spectre-v2 (via zero-shot prompt), returning all three outputs.

    Args:
        sarvam_client: Authenticated SarvamAI client.
        krutrim_native_client: KrutrimCloud native client (for KrutrimTranslate).
        krutrim_openai_client: OpenAI-compat Krutrim client (for LLM translation).
        text: Source text.
        src_sarvam: Source BCP-47 code (e.g. 'hi-IN').
        tgt_sarvam: Target BCP-47 code (e.g. 'en-IN').
        sarvam_translate_fn: Callable — typically sarvam_helpers.translate.
        reference: Optional human reference for display.

    Returns:
        Dict with keys: mayura, sarvam_translate, krutrim_translate, krutrim_llm.
    """
    from utils.krutrim_helpers import SARVAM_TO_KRUTRIM_LANG
    src_k = SARVAM_TO_KRUTRIM_LANG.get(src_sarvam, src_sarvam.split("-")[0])
    tgt_k = SARVAM_TO_KRUTRIM_LANG.get(tgt_sarvam, tgt_sarvam.split("-")[0])

    results: dict[str, str] = {}

    # Sarvam Mayura v1
    try:
        results["mayura"] = sarvam_translate_fn(
            sarvam_client, text, src=src_sarvam, tgt=tgt_sarvam, model="mayura:v1"
        )
    except Exception as e:
        results["mayura"] = f"[Error: {e}]"

    # Sarvam-Translate v1
    try:
        results["sarvam_translate"] = sarvam_translate_fn(
            sarvam_client, text, src=src_sarvam, tgt=tgt_sarvam,
            model="sarvam-translate:v1"
        )
    except Exception as e:
        results["sarvam_translate"] = f"[Error: {e}]"

    # Krutrim KrutrimTranslate (native SDK)
    try:
        results["krutrim_translate"] = krutrim_translate(
            krutrim_native_client, text, src=src_k, tgt=tgt_k
        )
    except Exception as e:
        results["krutrim_translate"] = f"[KrutrimTranslate unavailable: {e}]"

    # Krutrim LLM zero-shot translation
    try:
        from utils.krutrim_helpers import KRUTRIM_LANG_NAMES
        src_name = KRUTRIM_LANG_NAMES.get(src_k, src_k)
        tgt_name = KRUTRIM_LANG_NAMES.get(tgt_k, tgt_k)
        prompt = (
            f"Translate the following {src_name} text to {tgt_name}. "
            f"Output only the translation, nothing else.\n\n{text}"
        )
        results["krutrim_llm"] = krutrim_chat(
            krutrim_openai_client,
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
    except Exception as e:
        results["krutrim_llm"] = f"[Error: {e}]"

    # Print comparison
    print(f"\nSource: {text[:60]}")
    if reference:
        print(f"Reference:          {reference}")
    print(f"Mayura v1:          {results.get('mayura', 'N/A')[:80]}")
    print(f"Sarvam-Translate:   {results.get('sarvam_translate', 'N/A')[:80]}")
    print(f"KrutrimTranslate:   {results.get('krutrim_translate', 'N/A')[:80]}")
    print(f"Krutrim LLM (0-shot): {results.get('krutrim_llm', 'N/A')[:80]}")

    return results
