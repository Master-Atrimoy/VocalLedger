# 🎙️ Voice Expense Tracker

Log expenses by **voice or text** in natural language. Everything runs locally — no cloud APIs, no data leaks. Built with Whisper, Mistral 7B, LangChain, LangGraph, Hydra, Pydantic, FastAPI and Streamlit.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Streamlit UI                        │
│         Voice Input · Dashboard · Export                │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────┐
│                    FastAPI Backend                       │
│           /api/voice · /api/expenses · /api/analytics   │
└────┬──────────────────┬──────────────────────┬──────────┘
     │                  │                      │
┌────▼─────┐    ┌───────▼────────┐    ┌────────▼───────┐
│  Whisper │    │  LangGraph     │    │    SQLite      │
│   STT    │───▶│  Agent Graph   │───▶│   Database     │
│(local)   │    │  (pipeline)    │    │                │
└──────────┘    └───────┬────────┘    └────────────────┘
                        │
               ┌────────▼────────┐
               │   LangChain     │
               │  Mistral 7B via │
               │    Ollama       │
               └─────────────────┘
```

### LangGraph Pipeline

```
[transcribe] → [extract] → [resolve_date] → [validate] → END
                  ↑
                  └─── retry (max 2x on failure)
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| LLM | Mistral 7B via Ollama | Expense extraction from natural language |
| STT | faster-whisper (`base` / `medium`) | Voice transcription, runs fully local |
| Agent | LangGraph `StateGraph` | Orchestrates the transcribe → extract → validate pipeline |
| Chains | LangChain LCEL + `PydanticOutputParser` | Prompt → LLM → structured JSON |
| Config | Hydra Compose API + OmegaConf | Composable config: model / whisper / database overrides |
| Validation | Pydantic v2 | All API request/response and LLM output schemas |
| API | FastAPI | REST backend with lifespan dependency injection |
| DB | SQLAlchemy + SQLite | Expense persistence |
| UI | Streamlit | Voice log, dashboard, export |
| Eval | Custom evaluator | Extraction accuracy metrics + WER for STT |

---

## Quick Start

### 1. Install Ollama and pull the model

```bash
# Install Ollama: https://ollama.com
ollama pull mistral:7b
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

Or just:
```bash
make setup
```

### 3. Start the backend (Terminal 1)

```bash
make backend
# or: uvicorn backend.main:app --reload --port 8000
```

### 4. Start the frontend (Terminal 2)

```bash
make frontend
# or: streamlit run frontend/app.py
```

Open http://localhost:8501 in your browser.

---

## Configuration (Hydra)

All config lives in `conf/`. Override anything at runtime:

```bash
# Use llama3.2:3b instead of mistral
uvicorn backend.main:app --reload  # then set model=llama in config

# Use whisper medium for better multilingual support
# Edit conf/whisper/base.yaml → model_size: "medium"
# Or: make a conf/whisper/medium.yaml and set defaults in config.yaml
```

### Config files

```
conf/
├── config.yaml          ← Main config (sets defaults)
├── model/
│   ├── mistral.yaml     ← Mistral 7B settings
│   └── llama.yaml       ← Llama 3.2 3B (low-RAM fallback)
├── database/
│   └── sqlite.yaml      ← DB URL
└── whisper/
    ├── base.yaml        ← Fast, English-focused
    └── medium.yaml      ← Slower, better multilingual
```

---

## API Reference

### Voice

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/voice/audio` | Upload WAV/MP3 → transcribe → extract → save |
| POST | `/api/voice/text` | Natural language text → extract → save |

### Expenses

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/expenses/` | List with filters: `from_date`, `to_date`, `category` |
| GET | `/api/expenses/{id}` | Get single expense |
| PUT | `/api/expenses/{id}` | Update expense |
| DELETE | `/api/expenses/{id}` | Delete expense |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/summary` | Total + count for `period` (week/month/year) |
| GET | `/api/analytics/categories` | Breakdown by category with % |
| GET | `/api/analytics/daily` | Daily spend trend (last N days) |
| GET | `/api/analytics/dashboard` | All analytics in one call |
| GET | `/api/analytics/export` | Download CSV |

Full interactive docs at http://localhost:8000/docs

---

## Evaluation Layer

### Extraction Accuracy

Runs 25 hand-crafted test cases against the LLM chain. Measures:

- **Success rate** — did the model extract / correctly fail?
- **Amount accuracy** — within 1% tolerance
- **Category accuracy** — exact match
- **Payment accuracy** — exact match
- **Date accuracy** — today / yesterday / specific classification
- **Overall score** — weighted composite

```bash
make eval              # run with default model (mistral)
make eval-llama        # run with llama3.2:3b
```

Reports saved to `evaluation/reports/eval_YYYYMMDD_HHMMSS.md`

### STT Evaluation (WER)

Place reference pairs in `evaluation/stt_samples/`:
```
evaluation/stt_samples/001.wav
evaluation/stt_samples/001.txt   ← reference transcript
```

```bash
make eval-stt
```

Computes Word Error Rate (WER) and Character Error Rate (CER) per file.

---

## Running Tests

```bash
make test          # run all tests (mocked — no Ollama needed)
make test-cov      # with coverage report
```

Tests mock both Ollama and Whisper, so they run in CI without any local models.

---

## Project Structure

```
voice-expense-tracker/
├── conf/                        # Hydra config
│   ├── config.yaml
│   ├── model/{mistral,llama}.yaml
│   ├── database/sqlite.yaml
│   └── whisper/{base,medium}.yaml
├── backend/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # Hydra Compose API singleton
│   ├── dependencies.py          # FastAPI DI helpers
│   ├── schemas/expense.py       # All Pydantic models
│   ├── database/
│   │   ├── models.py            # SQLAlchemy ORM
│   │   └── db.py                # Engine + session factory
│   ├── services/
│   │   ├── stt.py               # faster-whisper wrapper
│   │   ├── llm_chain.py         # LangChain LCEL extraction chain
│   │   └── graph.py             # LangGraph StateGraph pipeline
│   └── routers/
│       ├── voice.py             # /api/voice/*
│       ├── expenses.py          # /api/expenses/*
│       └── analytics.py         # /api/analytics/*
├── frontend/
│   ├── app.py                   # Streamlit entry point
│   └── pages/
│       ├── 1_log.py             # Voice + text logging
│       ├── 2_dashboard.py       # Charts + transactions
│       └── 3_export.py          # CSV / JSON export
├── evaluation/
│   ├── test_cases.json          # 25 annotated test cases
│   ├── eval_extraction.py       # LLM accuracy evaluator
│   ├── eval_stt.py              # WER evaluator
│   └── reports/                 # Generated markdown reports
├── tests/
│   ├── test_llm.py              # Unit tests — LangChain chain
│   └── test_api.py              # Integration tests — FastAPI routes
├── requirements.txt
├── Makefile
└── docs/README.md               ← you are here
```

---

## Supported Input Formats

The LLM handles all of these naturally:

| Input | Extracted |
|-------|-----------|
| `spent 200 on groceries` | ₹200 · Food |
| `auto fare 85 yesterday cash` | ₹85 · Transport · cash |
| `2k shopping at Zara card` | ₹2000 · Shopping · card |
| `two hundred rupees at canteen` | ₹200 · Food |
| `₹450 petrol yesterday` | ₹450 · Transport |
| `paise diya 200 sabji ke liye` | ₹200 · Food (Hinglish) |
| `hello how are you` | ❌ no expense found |

---

## Low-RAM Mode (< 8 GB)

Switch to Llama 3.2 3B:
```bash
ollama pull llama3.2:3b
```
Edit `conf/config.yaml`:
```yaml
defaults:
  - model: llama   # ← change this
```

Use Whisper `tiny` for faster STT:
Edit `conf/whisper/base.yaml`:
```yaml
model_size: "tiny"
```

---

## Extending

**Add a new category** → edit `conf/config.yaml` → `extraction.categories` + update `ExpenseCategory` enum in `backend/schemas/expense.py` + add a test case in `evaluation/test_cases.json`.

**Switch LLM provider** → subclass `ExpenseExtractionChain`, swap `ChatOllama` for `ChatOpenAI` or any LangChain-compatible provider.

**Add budget alerts** → new analytics endpoint + Streamlit notification widget.

**Multi-user** → add a `user_id` column to the `Expense` table + JWT auth middleware.
