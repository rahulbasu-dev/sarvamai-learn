"""
Shared API wrappers and visualization helpers for Sarvam AI Indic NLP notebooks.
Handles authentication, rate limiting, retry logic, and cost estimation.
"""

import os
import time
import logging
import threading
from functools import wraps
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import pandas as pd
from dotenv import load_dotenv
from IPython.display import Audio, display

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()

DEMO_MODE: bool = os.getenv("DEMO_MODE", "False").lower() == "true"
_CALL_COUNTER: dict[str, int] = {}
_MAX_CALLS_PER_CELL = 3  # enforced when DEMO_MODE=True


def _check_demo_limit(call_key: str) -> None:
    """Raise RuntimeError if demo call limit exceeded."""
    if not DEMO_MODE:
        return
    _CALL_COUNTER[call_key] = _CALL_COUNTER.get(call_key, 0) + 1
    if _CALL_COUNTER[call_key] > _MAX_CALLS_PER_CELL:
        raise RuntimeError(
            f"DEMO_MODE: max {_MAX_CALLS_PER_CELL} calls reached for '{call_key}'. "
            "Set DEMO_MODE=False in .env to remove this cap."
        )


def reset_demo_counters() -> None:
    """Call at the start of each notebook cell to reset per-cell counters."""
    _CALL_COUNTER.clear()


# ---------------------------------------------------------------------------
# Rate Limiter (token bucket, 60 req/min default)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, max_calls: int = 60, period: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a request slot is available."""
        with self._lock:
            now = time.time()
            # Remove calls older than the period window
            self._calls = [t for t in self._calls if now - t < self.period]
            if len(self._calls) >= self.max_calls:
                sleep_time = self.period - (now - self._calls[0])
                logger.info("Rate limit: sleeping %.1fs", sleep_time)
                time.sleep(max(sleep_time, 0))
                self._calls = [t for t in self._calls if time.time() - t < self.period]
            self._calls.append(time.time())


_rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------
def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Exponential backoff on 429 / transient errors."""

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
                        delay = base_delay * (2**attempt)
                        logger.warning("429 – retrying in %.1fs (attempt %d/%d)", delay, attempt + 1, max_retries)
                        time.sleep(delay)
                    else:
                        raise
            return None  # unreachable

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Cost estimator
# ---------------------------------------------------------------------------
COST_RATES = {
    "text_per_10k_chars": 20.0,   # INR 20 per 10K chars (approximate)
    "audio_per_second": 0.5,      # INR 0.50 per second of TTS audio
}


def estimate_cost(text: Optional[str] = None, audio_seconds: float = 0.0) -> str:
    """Return a human-readable cost estimate string."""
    cost = 0.0
    if text:
        cost += (len(text) / 10_000) * COST_RATES["text_per_10k_chars"]
    cost += audio_seconds * COST_RATES["audio_per_second"]
    return f"Estimated cost: INR {cost:.4f}"


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------
def load_client():
    """Load .env, validate API key, return authenticated SarvamAI client."""
    load_dotenv(override=True)
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "SARVAM_API_KEY not found. Create a .env file with SARVAM_API_KEY=<your_key>"
        )
    try:
        from sarvamai import SarvamAI
    except ImportError as exc:
        raise ImportError("sarvamai package not installed. Run: pip install sarvamai") from exc
    logger.info("SarvamAI client initialised (DEMO_MODE=%s)", DEMO_MODE)
    return SarvamAI(api_subscription_key=api_key)


# ---------------------------------------------------------------------------
# API wrappers
# ---------------------------------------------------------------------------

@retry_with_backoff()
def translate(
    client,
    text: str,
    src: str = "en-IN",
    tgt: str = "hi-IN",
    mode: str = "formal",
    model: str = "mayura:v1",
) -> str:
    """Translate text using Sarvam Translation API.

    Args:
        client: Authenticated SarvamAI client.
        text: Source text (max 1000 chars recommended for demos).
        src: BCP-47 source language code.
        tgt: BCP-47 target language code.
        mode: formal | modern-colloquial | classic-colloquial | code-mixed.
        model: mayura:v1 | sarvam-translate:v1.

    Returns:
        Translated string.
    """
    _rate_limiter.acquire()
    _check_demo_limit("translate")
    print(estimate_cost(text=text))
    response = client.text.translate(
        input=text,
        source_language_code=src,
        target_language_code=tgt,
        speaker_gender="Female",
        mode=mode,
        model=model,
    )
    return response.translated_text


@retry_with_backoff()
def transliterate(
    client,
    text: str,
    src: str = "ta-IN",
    tgt: str = "en-IN",
) -> str:
    """Transliterate text between scripts.

    Args:
        client: Authenticated SarvamAI client.
        text: Source text.
        src: Source language code.
        tgt: Target language code (usually en-IN for Romanization).

    Returns:
        Transliterated string.
    """
    _rate_limiter.acquire()
    _check_demo_limit("transliterate")
    print(estimate_cost(text=text))
    response = client.text.transliterate(
        input=text,
        source_language_code=src,
        target_language_code=tgt,
    )
    return response.transliterated_text


@retry_with_backoff()
def detect_language(client, text: str) -> dict:
    """Detect language of text.

    Args:
        client: Authenticated SarvamAI client.
        text: Text to identify.

    Returns:
        Dict with keys: language_code, script, confidence (float 0-1).
    """
    _rate_limiter.acquire()
    _check_demo_limit("detect_language")
    response = client.text.identify_language(input=text)
    return {
        "language_code": response.language_code,
        "script": getattr(response, "script", "unknown"),
        "confidence": getattr(response, "confidence", 1.0),
    }


@retry_with_backoff()
def tts_audio(
    client,
    text: str,
    lang: str = "hi-IN",
    voice: str = "ritu",
    model: str = "bulbul:v3",
    temperature: float = 0.6,
) -> bytes:
    """Generate TTS audio.

    Args:
        client: Authenticated SarvamAI client.
        text: Text to synthesize (< 500 chars for demos).
        lang: BCP-47 language code.
        voice: Speaker voice name.
        model: bulbul:v3 (recommended) | bulbul:v2.
        temperature: 0.1 (flat) – 1.5 (expressive). v3 only.

    Returns:
        Raw audio bytes (WAV format).
    """
    _rate_limiter.acquire()
    _check_demo_limit("tts_audio")
    audio_secs_estimate = len(text) / 15  # rough chars-per-second estimate
    print(estimate_cost(text=text, audio_seconds=audio_secs_estimate))

    kwargs: dict = dict(
        text=text,
        target_language_code=lang,
        speaker=voice,
        model=model,
        enable_preprocessing=True,
        speech_sample_rate=22050,
    )
    if "v3" in model:
        kwargs["temperature"] = temperature

    response = client.text_to_speech.convert(**kwargs)
    # Response may be bytes directly or have an audio attribute
    if isinstance(response, bytes):
        return response
    if hasattr(response, "audios") and response.audios:
        import base64
        audio_b64 = response.audios[0]
        if isinstance(audio_b64, str):
            return base64.b64decode(audio_b64)
        return audio_b64
    if hasattr(response, "audio"):
        return response.audio
    return b""


@retry_with_backoff()
def chat_complete(
    client,
    messages: list[dict],
    reasoning_effort: str = "low",
    model: str = "sarvam-m:v1",
) -> str:
    """Chat completion via Sarvam-M.

    Args:
        client: Authenticated SarvamAI client.
        messages: List of {role, content} dicts (OpenAI-style).
        reasoning_effort: low | high. Use high only for showcase cells.
        model: Model identifier string.

    Returns:
        Assistant response string.
    """
    _rate_limiter.acquire()
    _check_demo_limit("chat_complete")
    total_chars = sum(len(m.get("content", "")) for m in messages)
    print(estimate_cost(text="x" * total_chars))
    response = client.chat.completions(
        messages=messages,
        reasoning_effort=reasoning_effort,
    )
    if hasattr(response, "choices"):
        return response.choices[0].message.content
    return str(response)


# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------

LANG_COLORS = {
    "hi-IN": "#FF6B35",   # saffron-orange
    "ta-IN": "#4ECDC4",   # teal
    "bn-IN": "#45B7D1",   # sky-blue
    "te-IN": "#96CEB4",   # sage-green
    "en-IN": "#888888",   # grey
}

LANG_NAMES = {
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "bn-IN": "Bengali",
    "te-IN": "Telugu",
    "en-IN": "English",
}


def plot_token_lengths(texts_dict: dict[str, str], title: str = "Word Token Count by Language") -> None:
    """Bar chart: whitespace-tokenized word count per language.

    Args:
        texts_dict: {lang_code: text_string}.
        title: Chart title.
    """
    langs = list(texts_dict.keys())
    counts = [len(t.split()) for t in texts_dict.values()]
    colors = [LANG_COLORS.get(l, "#CCCCCC") for l in langs]
    labels = [LANG_NAMES.get(l, l) for l in langs]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, counts, color=colors, edgecolor="white", linewidth=1.5)
    ax.bar_label(bars, padding=3, fontsize=11)
    ax.set_ylabel("Number of Tokens (whitespace split)")
    ax.set_title(title)
    ax.set_ylim(0, max(counts) * 1.2)
    sns.despine()
    plt.tight_layout()
    plt.show()


def plot_similarity_heatmap(
    matrix: np.ndarray,
    labels: list[str],
    title: str = "Semantic Similarity Heatmap",
) -> None:
    """Seaborn heatmap for similarity matrix.

    Args:
        matrix: N×N float array of similarity scores.
        labels: Axis tick labels.
        title: Chart title.
    """
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(
        matrix,
        xticklabels=labels,
        yticklabels=labels,
        annot=True,
        fmt=".2f",
        cmap="YlOrRd",
        vmin=0,
        vmax=1,
        linewidths=0.5,
        ax=ax,
    )
    ax.set_title(title, pad=14)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.show()


def plot_bleu_comparison(
    results_dict: dict[str, dict[str, float]],
    title: str = "BLEU Score Comparison",
) -> None:
    """Grouped bar chart: BLEU scores across models and languages.

    Args:
        results_dict: {model_name: {lang_code: bleu_score}}.
        title: Chart title.
    """
    models = list(results_dict.keys())
    langs = list(next(iter(results_dict.values())).keys())
    x = np.arange(len(langs))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, model in enumerate(models):
        scores = [results_dict[model].get(l, 0.0) for l in langs]
        offset = (i - len(models) / 2 + 0.5) * width
        bars = ax.bar(x + offset, scores, width, label=model, alpha=0.85)
        ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels([LANG_NAMES.get(l, l) for l in langs])
    ax.set_ylabel("BLEU Score")
    ax.set_title(title)
    ax.legend()
    ax.set_ylim(0, 1.0)
    sns.despine()
    plt.tight_layout()
    plt.show()


def plot_language_confidence(
    detections: dict[str, dict],
    title: str = "Language Detection Confidence",
) -> None:
    """Horizontal bar chart of detection confidences.

    Args:
        detections: {label: {language_code, confidence}}.
        title: Chart title.
    """
    labels = list(detections.keys())
    confidences = [d.get("confidence", 1.0) for d in detections.values()]
    lang_codes = [d.get("language_code", "?") for d in detections.values()]
    colors = [LANG_COLORS.get(lc, "#AAAAAA") for lc in lang_codes]

    fig, ax = plt.subplots(figsize=(9, max(3, len(labels) * 0.5)))
    bars = ax.barh(labels, confidences, color=colors, edgecolor="white")
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Confidence")
    ax.set_title(title)
    for bar, lc in zip(bars, lang_codes):
        ax.text(
            bar.get_width() + 0.01,
            bar.get_y() + bar.get_height() / 2,
            lc,
            va="center",
            fontsize=9,
        )
    sns.despine()
    plt.tight_layout()
    plt.show()


def plot_benchmark_table(df: pd.DataFrame, title: str = "Benchmark Results") -> None:
    """Display a color-styled pandas DataFrame as a table.

    Args:
        df: DataFrame with benchmark metrics.
        title: Title printed above the table.
    """
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    try:
        from IPython.display import display as ipy_display
        styled = df.style.background_gradient(cmap="Greens", axis=None).set_caption(title)
        ipy_display(styled)
    except Exception:
        print(df.to_string())


def display_audio_inline(audio_bytes: bytes, sample_rate: int = 22050, label: str = "") -> None:
    """Display audio inline in Jupyter using IPython.display.Audio.

    Args:
        audio_bytes: Raw audio bytes (WAV).
        sample_rate: Sample rate in Hz.
        label: Optional text label printed before the player.
    """
    if label:
        print(f"\n🔊 {label}")
    display(Audio(data=audio_bytes, rate=sample_rate, autoplay=False))


def plot_waveform(audio_bytes: bytes, sample_rate: int = 22050, title: str = "TTS Waveform") -> None:
    """Plot audio waveform from raw bytes.

    Args:
        audio_bytes: Raw PCM or WAV audio bytes.
        sample_rate: Sample rate in Hz.
        title: Chart title.
    """
    import io
    import wave
    import struct

    try:
        # Try reading as WAV
        with wave.open(io.BytesIO(audio_bytes)) as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            fmt = {1: "b", 2: "h", 4: "i"}.get(sampwidth, "h")
            samples = np.array(struct.unpack(f"<{n_frames * n_channels}{fmt}", raw))
            if n_channels > 1:
                samples = samples[::n_channels]  # take left channel
    except Exception:
        # Fall back: treat as raw int16
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)

    t = np.linspace(0, len(samples) / sample_rate, len(samples))
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(t, samples, linewidth=0.4, color="#FF6B35", alpha=0.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_title(title)
    sns.despine()
    plt.tight_layout()
    plt.show()


def plot_radar_chart(
    categories: list[str],
    model_scores: dict[str, list[float]],
    title: str = "Model Capability Radar",
) -> None:
    """Spider/radar chart for model capability comparison.

    Args:
        categories: Axis labels (e.g., ["Translation", "TTS", "ASR", ...]).
        model_scores: {model_name: [score_per_category]}.
        title: Chart title.
    """
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    palette = plt.cm.tab10.colors  # type: ignore[attr-defined]

    for idx, (model_name, scores) in enumerate(model_scores.items()):
        values = scores + scores[:1]
        color = palette[idx % len(palette)]
        ax.plot(angles, values, "o-", linewidth=2, color=color, label=model_name)
        ax.fill(angles, values, alpha=0.15, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=10)
    ax.set_ylim(0, 10)
    ax.set_title(title, y=1.1, fontsize=13)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1))
    plt.tight_layout()
    plt.show()
