"""Page 4 — Splits. LLM-first: describe it, AI builds everything."""
import streamlit as st
import requests
from audio_recorder_streamlit import audio_recorder
from datetime import date, timedelta
import dateparser

st.set_page_config(page_title="Splits", page_icon="🤝", layout="wide")
API = st.session_state.get("api_url", "http://localhost:8000")

# ── session state ─────────────────────────────────────────────────────────────
for k in ("split_preview", "show_split_form", "split_transcript"):
    if k not in st.session_state:
        st.session_state[k] = None if k != "show_split_form" else False

# ── helpers ───────────────────────────────────────────────────────────────────
def api_get(ep, params=None):
    try:
        r = requests.get(f"{API}{ep}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def api_post(ep, **kw):
    try:
        r = requests.post(f"{API}{ep}", timeout=120, **kw)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", e.response.text[:200])
        except Exception:
            detail = e.response.text[:200] or str(e)
        st.error(f"Error: {detail}")
        return None
    except Exception as e:
        st.error(str(e))
        return None

def api_patch(ep):
    try:
        r = requests.patch(f"{API}{ep}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(str(e))
        return None

def reset_split():
    st.session_state.split_preview = None
    st.session_state.show_split_form = False
    st.session_state.split_transcript = None

# ── Fetch people ONCE — reused across all tabs ────────────────────────────────
people       = api_get("/api/splits/people") or []
people_map   = {p["name"]: p["id"] for p in people}
people_names = list(people_map.keys())
self_person  = next((p for p in people if p["is_self"]), None)

# ── Page ──────────────────────────────────────────────────────────────────────
st.title("🤝 Splits")

tab_new, tab_bal, tab_hist, tab_settle, tab_people = st.tabs([
    "🎤 New Split", "💰 Balances", "📋 History", "✅ Settle Up", "👥 People"
])

# ════════════════════════════════════════════════════════════════════════════
# NEW SPLIT — LLM-first with voice input
# ════════════════════════════════════════════════════════════════════════════
with tab_new:

    if not st.session_state.show_split_form:
        st.markdown("### Describe the split")
        st.caption("Just say what happened — AI extracts details and creates people automatically.")

        # Voice input
        st.markdown("**🎤 Record**")
        audio_bytes = audio_recorder(
            text="Click to record",
            recording_color="#e74c3c",
            neutral_color="#2c3e50",
            icon_size="2x",
            pause_threshold=3.0,
            sample_rate=41_000,
            key="split_recorder",
        )
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            if st.button("Transcribe", key="transcribe_split"):
                with st.spinner("Transcribing..."):
                    try:
                        r = requests.post(
                            f"{API}/api/voice/audio",
                            files={"file": ("split.wav", audio_bytes, "audio/wav")},
                            timeout=120,
                        )
                        r.raise_for_status()
                        st.session_state.split_transcript = r.json().get("transcript", "")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Transcription failed: {e}")

        if st.session_state.split_transcript:
            st.info(f"Transcript: *{st.session_state.split_transcript}*")

        st.markdown("**Or type it:**")
        examples = [
            "Split 1800 dinner with Rahul and Priya, I paid",
            "Amit paid 2400 for hotel, split 4 ways between me, Amit, Sneha and Rohan",
            "Split yesterday's cab 350 with Kavya, she paid",
            "I paid 900 for groceries, split equally with Neha",
        ]
        example = st.selectbox("Try an example →", [""] + examples, key="split_example")
        split_text = st.text_area(
            "Describe the split",
            value=st.session_state.split_transcript or example,
            height=100,
            placeholder="e.g. Split 1800 dinner with Rahul and Priya, I paid",
            label_visibility="collapsed",
        )

        if st.button("✨ Parse & Preview", type="primary", disabled=not (split_text or "").strip()):
            with st.spinner("Understanding the split..."):
                result = api_post("/api/splits/smart-split",
                                  params={"text": split_text.strip()})
            if result:
                st.session_state.split_preview = result
                st.session_state.show_split_form = True
                st.session_state.split_transcript = None
                st.rerun()

    else:
        # Refresh people after auto-creation
        people       = api_get("/api/splits/people") or []
        people_map   = {p["name"]: p["id"] for p in people}
        people_names = list(people_map.keys())

        preview = st.session_state.split_preview

        if preview.get("auto_created"):
            st.info(f"✨ Auto-created: **{', '.join(preview['auto_created'])}**")

        st.markdown("### Review & Confirm")

        with st.form("confirm_split"):
            col1, col2 = st.columns(2)
            with col1:
                desc  = st.text_input("Description", value=preview["description"])
                total = st.number_input("Total (₹)", value=float(preview["total_amount"]),
                                        min_value=0.01, step=10.0)
                # Resolve date
                ds = preview.get("date_str", "today")
                if ds == "today":
                    dval = date.today()
                elif ds == "yesterday":
                    dval = date.today() - timedelta(days=1)
                else:
                    parsed = dateparser.parse(ds)
                    dval = parsed.date() if parsed else date.today()
                split_date = st.date_input("Date", value=dval)

            with col2:
                payer_default = preview["paid_by_name"]
                payer_idx = people_names.index(payer_default) if payer_default in people_names else 0
                paid_by    = st.selectbox("Paid by", people_names, index=payer_idx)
                split_type = st.radio("Split type", ["equal", "custom"], horizontal=True)

            st.markdown("**Shares**")
            shares = preview.get("shares_preview", [])
            n_cols = min(len(shares), 4)
            cols = st.columns(n_cols) if n_cols > 0 else [st.columns(1)[0]]
            edited_shares = []
            for i, share in enumerate(shares):
                col = cols[i % n_cols]
                with col:
                    p_name = share["person_name"]
                    p_idx  = people_names.index(p_name) if p_name in people_names else 0
                    sel_name = st.selectbox(f"Person {i+1}", people_names,
                                            index=p_idx, key=f"sp_n_{i}")
                    if split_type == "custom":
                        amt = st.number_input("₹", value=float(share["share_amount"]),
                                              min_value=0.0, step=10.0, key=f"sp_a_{i}")
                    else:
                        st.write(f"₹{share['share_amount']:,.0f}")
                        amt = share["share_amount"]
                    edited_shares.append({
                        "person_id":    people_map.get(sel_name, share["person_id"]),
                        "person_name":  sel_name,
                        "share_amount": amt,
                    })

            col_save, col_cancel = st.columns([3, 1])
            save   = col_save.form_submit_button("💾 Save Split", type="primary", use_container_width=True)
            cancel = col_cancel.form_submit_button("✕ Cancel", use_container_width=True)

        if save:
            payload = {
                "description": desc, "total_amount": total,
                "paid_by_person_id": people_map.get(paid_by, edited_shares[0]["person_id"]),
                "split_type": split_type,
                "participant_ids": [s["person_id"] for s in edited_shares],
                "date": str(split_date),
            }
            if split_type == "custom":
                payload["custom_shares"] = [
                    {"person_id": s["person_id"], "share_amount": s["share_amount"]}
                    for s in edited_shares
                ]
            result = api_post("/api/splits/events", json=payload)
            if result:
                st.success(f"✅ Split saved — ₹{total:,.0f} split {len(edited_shares)} ways")
                reset_split()
                st.rerun()

        if cancel:
            reset_split()
            st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# BALANCES
# ════════════════════════════════════════════════════════════════════════════
with tab_bal:
    if not self_person:
        st.warning("⚠️ You haven't set yourself up yet.")
        st.info("Go to the **People** tab → Add yourself → check **'This is me'**. "
                "Balances are always calculated from your perspective.")
    else:
        data = api_get("/api/splits/balances")
        if not data:
            st.error("Could not load balances.")
        elif not data["balances"]:
            st.success("All settled up! 🎉")
        else:
            c1, c2, c3 = st.columns(3)
            net = data["net"]
            c1.metric("They Owe You", f"₹{data['total_you_are_owed']:,.0f}")
            c2.metric("You Owe",      f"₹{data['total_you_owe']:,.0f}")
            c3.metric("Net", f"₹{abs(net):,.0f}",
                      delta="you're owed" if net >= 0 else "you owe",
                      delta_color="normal" if net >= 0 else "inverse")
            st.markdown("---")
            for b in data["balances"]:
                col_n, col_s = st.columns([3, 2])
                col_n.write(f"**{b['person_name']}**")
                if b["net_amount"] > 0:
                    col_s.success(f"Owes you ₹{b['owes_you']:,.0f}")
                else:
                    col_s.error(f"You owe ₹{b['you_owe']:,.0f}")

# ════════════════════════════════════════════════════════════════════════════
# HISTORY
# ════════════════════════════════════════════════════════════════════════════
with tab_hist:
    events = api_get("/api/splits/events") or []
    if not events:
        st.info("No splits yet.")
    for ev in events[:20]:
        with st.expander(
            f"**{ev['description']}** — ₹{ev['total_amount']:,.0f}  ·  "
            f"{ev['date']}  ·  paid by {ev['paid_by_name']}"
        ):
            for share in ev["shares"]:
                cn, ca, cs = st.columns([3, 2, 2])
                cn.write(share["person_name"])
                ca.write(f"₹{share['share_amount']:,.0f}")
                if share["is_settled"]:
                    cs.success("Settled ✓")
                else:
                    if cs.button("Mark settled", key=f"s_{share['id']}"):
                        api_patch(f"/api/splits/events/{ev['id']}/shares/{share['id']}/settle")
                        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# SETTLE UP
# ════════════════════════════════════════════════════════════════════════════
with tab_settle:
    st.subheader("Record a Payment")
    st.caption("When someone pays you back (or you pay them), record it here.")

    if len(people) < 2:
        st.info("Add at least 2 people to record settlements.")
    else:
        with st.form("settle_form"):
            c1, c2 = st.columns(2)
            with c1:
                from_p = st.selectbox("Who paid", people_names)
                amount = st.number_input("Amount (₹)", min_value=1.0, step=10.0)
            with c2:
                to_p   = st.selectbox("Paid to", [n for n in people_names if n != from_p])
                s_date = st.date_input("Date", value=date.today())
            notes = st.text_input("Notes (optional)")
            if st.form_submit_button("Record", type="primary"):
                r = api_post("/api/splits/settlements", json={
                    "from_person_id": people_map[from_p],
                    "to_person_id":   people_map[to_p],
                    "amount": amount, "date": str(s_date),
                    "notes": notes or None,
                })
                if r:
                    st.success(f"Recorded: {from_p} → {to_p} ₹{amount:,.0f}")
                    st.rerun()

        st.markdown("---")
        settlements = api_get("/api/splits/settlements") or []
        for s in settlements[:15]:
            st.write(
                f"**{s['from_person_name']}** → **{s['to_person_name']}** "
                f"₹{s['amount']:,.0f} on {s['date']}"
                + (f"  · {s['notes']}" if s.get("notes") else "")
            )

# ════════════════════════════════════════════════════════════════════════════
# PEOPLE — backup/edit, not a prerequisite
# ════════════════════════════════════════════════════════════════════════════
with tab_people:
    st.caption("People are created automatically when you describe a split. "
               "Use this tab to edit contacts or set yourself up.")

    col_form, col_list = st.columns([2, 3])
    with col_form:
        st.markdown("**Add manually**")
        with st.form("add_person"):
            name    = st.text_input("Name")
            phone   = st.text_input("Phone (optional)")
            upi     = st.text_input("UPI ID (optional)")
            is_self = st.checkbox("This is me")
            if st.form_submit_button("Add"):
                if name:
                    r = api_post("/api/splits/people", json={
                        "name": name, "phone": phone or None,
                        "upi_id": upi or None, "is_self": is_self,
                    })
                    if r:
                        st.success(f"Added {name}")
                        st.rerun()

    with col_list:
        if not people:
            st.info("No people yet — they'll appear after your first split.")
        for p in people:
            cn, cd, ct = st.columns([3, 1, 1])
            cn.write(f"**{p['name']}**" +
                     (f"  ·  {p.get('phone','')}" if p.get("phone") else ""))
            if p["is_self"]:
                ct.success("You")
            if cd.button("✕", key=f"dp_{p['id']}"):
                requests.delete(f"{API}/api/splits/people/{p['id']}", timeout=10)
                st.rerun()
