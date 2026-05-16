"""Page 1 — Log a transaction by voice or text."""
import streamlit as st
import requests
from audio_recorder_streamlit import audio_recorder
from datetime import date

st.set_page_config(page_title="Log Transaction", page_icon="🎙️", layout="centered")

API = st.session_state.get("api_url", "http://localhost:8000")

CATEGORIES     = ["Food","Transport","Shopping","Bills","Health","Entertainment","Income","Other"]
PAYMENT_METHODS = ["unknown","cash","card","upi"]
TX_TYPES       = ["expense","income"]

# ── session state init ────────────────────────────────────────────────────────
for k in ("extraction_result", "show_form"):
    if k not in st.session_state:
        st.session_state[k] = None if k != "show_form" else False

# ── helpers ───────────────────────────────────────────────────────────────────
def _safe_detail(e):
    try:
        return e.response.json().get("detail", str(e))
    except Exception:
        return e.response.text.strip() or f"HTTP {e.response.status_code}"

def post_audio(audio_bytes):
    r = requests.post(f"{API}/api/voice/audio",
                      files={"file": ("recording.wav", audio_bytes, "audio/wav")},
                      timeout=120)
    r.raise_for_status()
    return r.json()

def post_text(text):
    r = requests.post(f"{API}/api/voice/text", data={"text": text}, timeout=60)
    r.raise_for_status()
    return r.json()

def update_expense(expense_id, payload):
    r = requests.put(f"{API}/api/expenses/{expense_id}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def discard_expense(expense_id):
    requests.delete(f"{API}/api/expenses/{expense_id}", timeout=10)

def reset():
    st.session_state.extraction_result = None
    st.session_state.show_form = False

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🎙️ Log Transaction")
st.caption("Expenses and income — speak or type naturally.")

# ── Input tabs (hidden once a result is pending) ──────────────────────────────
if not st.session_state.show_form:

    tab_voice, tab_text = st.tabs(["🎤 Voice", "⌨️ Text"])

    with tab_voice:
        st.markdown("Click the mic, speak, click again to stop.")
        audio_bytes = audio_recorder(
            text="Click to record",
            recording_color="#e74c3c",
            neutral_color="#2c3e50",
            icon_size="2x",
            pause_threshold=3.0,
            sample_rate=41_000,
        )
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            if st.button("📤 Transcribe & Extract", type="primary"):
                with st.spinner("Transcribing..."):
                    try:
                        result = post_audio(audio_bytes)
                        st.session_state.extraction_result = result
                        st.session_state.show_form = True
                        st.rerun()
                    except requests.HTTPError as e:
                        st.error(f"Extraction failed: {_safe_detail(e)}")
                    except requests.exceptions.ConnectionError:
                        st.error("Backend unreachable — is uvicorn running on port 8000?")
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")

    with tab_text:
        examples = [
            "spent 200 on groceries at Big Bazaar",
            "auto fare 85 rupees yesterday, paid cash",
            "got 1200 from students for tuition fees",
            "received salary 45000",
            "electricity bill 1200 via upi",
            "2k shopping at Zara, swiped card",
        ]
        example = st.selectbox("Try an example →", [""] + examples)
        text_input = st.text_area(
            "Describe your transaction",
            value=example,
            height=80,
            placeholder="e.g. spent 200 on groceries",
        )
        if st.button("📤 Extract", type="primary"):
            if text_input.strip():
                with st.spinner("Extracting..."):
                    try:
                        result = post_text(text_input.strip())
                        st.session_state.extraction_result = result
                        st.session_state.show_form = True
                        st.rerun()
                    except requests.HTTPError as e:
                        st.error(f"Extraction failed: {_safe_detail(e)}")
                    except requests.exceptions.ConnectionError:
                        st.error("Backend unreachable — is uvicorn running on port 8000?")
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")
            else:
                st.warning("Enter something first.")

# ── Confirmation form — persists across reruns via session_state ──────────────
if st.session_state.show_form and st.session_state.extraction_result:
    result = st.session_state.extraction_result
    exp    = result["expense"]
    tx     = exp.get("transaction_type", "expense")
    icon   = "💸" if tx == "expense" else "💰"

    st.markdown("---")
    st.subheader(f"{icon} Review & Confirm")

    # Editable transcript — correct STT errors before re-extracting
    st.markdown("**Transcript** *(edit if Whisper got it wrong, then re-extract)*")
    col_t, col_btn = st.columns([4, 1])
    with col_t:
        edited = st.text_input("transcript", value=result.get("transcript", ""),
                               label_visibility="collapsed")
    with col_btn:
        if st.button("🔄 Re-extract"):
            discard_expense(exp["id"])
            with st.spinner("Re-extracting..."):
                try:
                    new_result = post_text(edited)
                    st.session_state.extraction_result = new_result
                    st.rerun()
                except Exception as e:
                    st.error(f"Re-extract failed: {e}")

    st.markdown("---")

    # All fields inside st.form — no per-widget reruns
    with st.form("confirm_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_type    = st.selectbox("Type", TX_TYPES,
                                       index=TX_TYPES.index(tx) if tx in TX_TYPES else 0)
            new_amount  = st.number_input("Amount (₹)", value=float(exp["amount"]),
                                          min_value=0.01, step=1.0)
            new_date    = st.date_input("Date", value=date.fromisoformat(exp["date"]))
        with col2:
            new_cat     = st.selectbox("Category", CATEGORIES,
                                       index=CATEGORIES.index(exp["category"])
                                       if exp["category"] in CATEGORIES else 0)
            new_payment = st.selectbox("Payment", PAYMENT_METHODS,
                                       index=PAYMENT_METHODS.index(exp["payment_method"])
                                       if exp["payment_method"] in PAYMENT_METHODS else 0)
            new_desc    = st.text_input("Description", value=exp.get("description") or "")

        conf = result.get("extraction_confidence", 0)
        lang = result.get("language_detected") or "—"
        st.caption(f"Confidence: {conf*100:.0f}%  ·  Language: {lang}")

        col_save, col_discard = st.columns([3, 1])
        save    = col_save.form_submit_button("💾 Save", type="primary", use_container_width=True)
        discard = col_discard.form_submit_button("🗑️ Discard", use_container_width=True)

    if save:
        try:
            update_expense(exp["id"], {
                "amount": new_amount, "currency": "INR",
                "category": new_cat, "description": new_desc,
                "date": str(new_date), "payment_method": new_payment,
                "transaction_type": new_type, "raw_text": exp.get("raw_text"),
            })
            label = "income" if new_type == "income" else "expense"
            st.success(f"✅ Saved — ₹{new_amount:,.0f} {label} ({new_cat})")
            reset()
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")

    if discard:
        discard_expense(exp["id"])
        st.info("Discarded.")
        reset()
        st.rerun()
