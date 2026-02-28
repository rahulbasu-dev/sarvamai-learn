# Sarvam AI — Indic NLP Educational Notebook Suite

A self-contained Jupyter notebook course that uses **Sarvam AI's live APIs** as
a practical lens on the NLP concepts taught in *Speech and Language Processing*
(Jurafsky & Martin). Every notebook pairs rigorous linguistic theory with
runnable API calls, quantitative experiments, rich visualisations, and
deliberate failure-mode demonstrations — all applied to Hindi, Tamil, Bengali,
and Telugu, where English-centric NLP assumptions break down in instructive ways.

---

## Quick Start (Cloud VM)

On a fresh **Ubuntu 22.04+** VM (AWS, GCP, Azure, etc.):

```bash
git clone https://github.com/rahulbasu-dev/sarvamai-learn.git
cd sarvamai-learn
bash setup.sh        # installs everything, prompts for API keys
bash run.sh          # launches JupyterLab on port 8888
```

`setup.sh` handles system packages, Python venv, pip dependencies, NLTK data,
`.env` configuration, and a smoke test — all in one command. It is idempotent
and safe to re-run.

> **Firewall**: open port **8888** in your cloud console's security group /
> firewall rules so you can access JupyterLab from your browser.

---

## Quick Start (Local Machine)

### 1. Clone the repo

```bash
git clone https://github.com/rahulbasu-dev/sarvamai-learn.git
cd sarvamai-learn
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # Linux / macOS
# or: venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your SARVAM_API_KEY
```

Get your API key from [sarvam.ai](https://sarvam.ai). Set `DEMO_MODE=True`
(default) to cap each cell at 3 API calls — prevents accidental runaway spend
during classroom demos.

### 5. Launch Jupyter

```bash
jupyter lab
```

Navigate to `notebooks/` and start with **00_setup_and_orientation.ipynb**.

---

## Who This Is For

NLP instructors and students who have read (or are reading) *Speech and
Language Processing* and want to see the same concepts — tokenisation, morphology,
vector semantics, sequence labelling, transformers, machine translation, and
speech processing — play out on real Indic language data, with a live production
API instead of toy examples.

---

## Project Structure

```
sarvamai-learn/
├── .env.example              # Template for API keys (copy to .env)
├── requirements.txt          # All Python dependencies
├── setup.sh                  # One-click cloud VM setup
├── run.sh                    # Launch JupyterLab for remote access
│
├── data/
│   └── sample_texts.py       # Canonical Hindi / Tamil / Bengali / Telugu
│                              # constants imported by every notebook
│
├── utils/
│   ├── sarvam_helpers.py     # Authenticated API wrappers, rate limiter,
│   │                         # cost estimator, and visualisation helpers
│   └── krutrim_helpers.py    # Krutrim AI API wrappers
│
├── notebooks/
│   ├── 00_setup_and_orientation.ipynb
│   ├── 01_tokenization_morphology.ipynb
│   ├── 02_vector_semantics_embeddings.ipynb
│   ├── 03_sequence_labeling_structure.ipynb
│   ├── 04_neural_mt_transformers.ipynb
│   ├── 05_speech_processing.ipynb
│   └── 06_model_comparisons_benchmarks.ipynb
│
└── outputs/                  # Created by setup.sh
    ├── audio/                # .wav files from TTS demos
    └── figures/              # PNG charts from matplotlib cells
```

---

## Notebook Coverage

| # | Notebook | Core Concepts | APIs Used |
|---|----------|--------------|-----------|
| 00 | Setup & Orientation | Why Indic NLP is hard; 22 languages, 10+ scripts; model family overview | Language Detection |
| 01 | Tokenisation & Morphology | Whitespace tokenisation, BPE fragmentation, agglutination (Tamil), sandhi (Hindi), code-mixing | Transliteration, Language Detection |
| 02 | Vector Semantics & Embeddings | Distributional hypothesis, word2vec/SGNS, cross-lingual embeddings, multilingual alignment | Translation, Chat Completions |
| 03 | Sequence Labeling & Structure | POS tagging (UD tagset), HMM vs CRF vs neural, free word order, NER, code-mixing | Chat Completions, Translation |
| 04 | Neural MT & Transformers | Encoder-decoder, cross-attention, IBM alignment, low-resource MT, BLEU | Translation, Chat Completions |
| 05 | Speech Processing | ASR pipeline, acoustic models, WER, TTS neural synthesis, temperature, prosody | TTS (Bulbul v3), STT (Saaras v3) |
| 06 | Model Comparisons & Benchmarks | BLEU/WER/F1/CER, IndicGLUE, IN22, Vistaar, LLM-as-judge | Translation, Chat Completions |

### Bonus Cells
Cells marked **⭐ Bonus** appear at the end of each relevant notebook section.
They require additional pip installs (`transformers`, `sentence-transformers`,
`torch`) and are clearly separated so time-pressed students can skip them.

---

## APIs Covered

### Sarvam AI

| API | Model | Notebooks |
|-----|-------|-----------|
| Language Detection | — | 00, 01 |
| Transliteration | — | 01, 02 |
| Translation | Mayura v1, Sarvam-Translate v1 | 02, 03, 04, 06 |
| Chat Completions | Sarvam-M 24B | 02, 03, 04, 06 |
| Text-to-Speech | Bulbul v3 | 05, 06 |
| Speech-to-Text | Saaras v2/v3 | 05 |

### Krutrim AI (comparison cells)

Krutrim cells require `KRUTRIM_CLOUD_API_KEY` in `.env`. They gracefully skip
if the key is absent — all Sarvam cells work without a Krutrim key.

---

## Prerequisites

- **Python 3.10+**
- A **Sarvam AI API key** ([sarvam.ai](https://sarvam.ai))
- ~500 MB disk for model downloads (bonus cells only)
- For cloud: an **Ubuntu 22.04+** VM with port 8888 open

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `EnvironmentError: SARVAM_API_KEY not found` | Create `.env` in project root with your key (see `.env.example`) |
| `ModuleNotFoundError: No module named 'sarvamai'` | Run `pip install -r requirements.txt` inside the activated venv |
| `RuntimeError: DEMO_MODE: max 3 calls reached` | Add `reset_demo_counters()` at cell top, or set `DEMO_MODE=False` |
| Jupyter shows garbled Indic text | Install [Noto Sans](https://fonts.google.com/noto) fonts and restart Jupyter |
| `torch` install very slow | Use `pip install torch --index-url https://download.pytorch.org/whl/cpu` for CPU-only |

---

## Rate Limits & Cost

`utils/sarvam_helpers.py` includes a built-in rate limiter (60 req/min) and
prints an INR cost estimate before every API call. With `DEMO_MODE=True`, a
full run of all 7 notebooks costs under ₹7.

---

## Textbook Alignment

Every notebook maps to chapters in *Speech and Language Processing*
(Jurafsky & Martin, 3rd ed. draft):

| Notebook | Chapters |
|----------|---------|
| 01 | Text Normalization (Ch. 2), Morphology (Ch. 4) |
| 02 | Vector Semantics & Embeddings (Ch. 6) |
| 03 | Sequence Labeling (Ch. 8), Syntactic Parsing (Ch. 9) |
| 04 | Transformers (Ch. 10), Machine Translation (Ch. 13) |
| 05 | Speech Recognition & Synthesis (Ch. 16) |
| 06 | Evaluation methodology (throughout) |

---

## License

See [LICENSE](LICENSE) for details.
