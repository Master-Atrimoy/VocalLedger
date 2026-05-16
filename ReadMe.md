# Voice Expense Tracker

A local-first personal finance app. Log expenses and income by speaking naturally,
split bills with friends, and get pattern insights from your spending history.
Nothing leaves your machine — no accounts, no cloud, no subscription.

---

## Why this exists

Most expense trackers want you to manually enter every transaction, connect your
bank account, or pay a monthly fee to see your own spending data. The ones that
do offer voice input send your audio to a cloud server you don't control.

This app runs entirely on your machine. No account. No internet required after
setup. Your financial data stays in a SQLite file on your own disk.

The other thing it does differently is understand how people actually talk about
money — not just structured commands. You can say "grabbed lunch for 280, paid
cash" or "Rahul cleared his dues, got 500 from him" and it figures out what to
log. It also handles income, not just expenses, so you can use it as a full
personal ledger rather than just an expense tracker.

It won't replace a full accounting tool if you need one. But if you want a fast,
private way to track where your money is going without giving that information
to a third party, this is that.

---

## What it does

You speak or type something like:

> *"spent 450 on groceries at Big Bazaar"*
> *"got 1200 from students for tuition fees"*
> *"Split 1800 dinner with Rahul and Priya, I paid"*

The app transcribes your voice locally using Whisper, extracts the transaction
details using a local LLM (Mistral via Ollama), and saves it. That's the core loop.

On top of that:

- **Ledger** — tracks both expenses and income. Net balance shown on the dashboard.
- **Splits** — describe a bill split in plain English. People are created automatically,
  no manual setup needed. Tracks who owes whom and by how much.
- **Insights** — after 2 weeks of data, surfaces patterns: spending spikes, recurring
  bills, weekend vs weekday habits, monthly summary.
- **Model switching** — swap between any locally available Ollama model from the sidebar
  without restarting anything.

---

## Setup

You need [Ollama](https://ollama.com) installed and running.

```bash
ollama pull mistral:7b
ollama serve
```

Then in the project folder:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
streamlit run frontend/app.py
```

Open **http://localhost:8501**

On Windows you can use the batch file instead:

```bat
run.bat setup      # first time only — installs deps + pulls model
run.bat backend    # terminal 1
run.bat frontend   # terminal 2
```

---

## First time

The app expects Ollama to be running before the backend starts. If the sidebar
shows the backend as offline, make sure `ollama serve` is running first.

For splits, go to the **People** tab and add yourself with the "This is me" checkbox
checked. This is how the balance calculation knows whose perspective to use.

---

## Performance notes

On CPU (no GPU), Mistral 7B takes 45–90 seconds on the first inference after
startup while the model loads into memory. Subsequent calls are 10–20 seconds.
If that's too slow, switch to `llama3.2:3b` from the model picker in the sidebar.

To use a different model by default, edit `conf/model/mistral.yaml` and change
`model_id` to whatever `ollama list` shows on your machine.

---

## Voice input tips

The recorder stops after 3 seconds of silence. Speak clearly, pause briefly,
then it stops on its own. If Whisper mishears something, the transcript is editable
before extraction — fix it and click Re-extract without re-recording.

Currently handles one transaction per recording. If you say two things in one
sentence, it picks the first one. Multi-transaction input is planned for v2.

---

Evaluation

If you want to test how well the LLM extraction is working on your machine:

```bash
python -m evaluation.eval_extraction
```

This runs 25 hand-written test cases and shows accuracy per field (amount, category,
payment method, date). Reports saved to `evaluation/reports/`.

---

## Folder structure

backend/        FastAPI app, LangGraph pipeline, services
frontend/       Streamlit pages (log, dashboard, export, splits, insights)
conf/           Hydra config — model, whisper, database settings
evaluation/     Test cases and accuracy scripts
tests/          Pytest suite (mocked, no Ollama needed)

---

## Known limitations (v1)

- One transaction per voice input
- Split parsing handles one bill at a time — not a full group trip narrative
- Insights need at least 14 days of data to generate
- Runs on CPU by default — Whisper and Ollama both benefit significantly from a GPU
