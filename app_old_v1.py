"""
OMOP Mapping Curation Queue — local Streamlit app
Run: streamlit run app.py
"""
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from neo4j_utils import (
    get_driver, get_unmapped_terms, search_concepts,
    write_propose, write_confirm, write_skip
)

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OMOP Curation Queue",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 OMOP Mapping Curation Queue")

# ── Sidebar: connection config ────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Connection")
    neo4j_uri  = st.text_input("Neo4j URI",      value=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_db   = st.text_input("Database",        value=os.getenv("NEO4J_DATABASE", "neo4j"))
    neo4j_user = st.text_input("Username",        value=os.getenv("NEO4J_USERNAME", "neo4j"))
    neo4j_pass = st.text_input("Password",        value=os.getenv("NEO4J_PASSWORD", ""), type="password")
    openai_key = st.text_input("OpenAI API Key",  value=os.getenv("OPENAI_API_KEY", ""), type="password")
    curator    = st.text_input("Your name",       value="curator_1",
                               help="Written into the audit trail on every mapping")

    st.divider()
    connect_btn = st.button("🔌 Connect & Load Queue", use_container_width=True)

    st.divider()
    st.caption("**Keyboard shortcuts**")
    st.caption("P = Propose  |  C = Confirm  |  S = Skip")

# ── Session state ─────────────────────────────────────────────────────────────
if "driver"        not in st.session_state: st.session_state.driver        = None
if "queue"         not in st.session_state: st.session_state.queue         = []
if "selected_idx"  not in st.session_state: st.session_state.selected_idx  = 0
if "candidates"    not in st.session_state: st.session_state.candidates    = []
if "searching"     not in st.session_state: st.session_state.searching     = False
if "last_action"   not in st.session_state: st.session_state.last_action   = None
if "done_count"    not in st.session_state: st.session_state.done_count    = 0

# ── Connect & load ────────────────────────────────────────────────────────────
if connect_btn:
    try:
        driver = get_driver(neo4j_uri, neo4j_user, neo4j_pass)
        driver.verify_connectivity()
        st.session_state.driver  = driver
        terms = get_unmapped_terms(driver, neo4j_db)
        st.session_state.queue   = terms
        st.session_state.selected_idx = 0
        st.session_state.candidates   = []
        st.sidebar.success(f"✅ Connected — {len(terms)} unmapped terms")
    except Exception as e:
        st.sidebar.error(f"Connection failed: {e}")

# ── Guard: not connected ──────────────────────────────────────────────────────
if not st.session_state.driver:
    st.info("👈 Enter your Neo4j credentials in the sidebar and click **Connect & Load Queue**.")
    st.stop()

queue = st.session_state.queue
if not queue:
    st.success("🎉 No unmapped terms remaining!")
    st.stop()

# ── Layout: left queue | right review panel ───────────────────────────────────
col_queue, col_review = st.columns([1, 2], gap="large")

# ── LEFT: Queue table ─────────────────────────────────────────────────────────
with col_queue:
    st.subheader(f"Queue ({len(queue)} remaining)")

    # Filter controls
    vendors = sorted(set(t["vendor"] for t in queue))
    vendor_filter = st.multiselect("Filter by vendor", vendors, default=vendors, key="vf")

    filtered = [t for t in queue if t["vendor"] in vendor_filter]

    if not filtered:
        st.warning("No terms match the filter.")
        st.stop()

    # Build display table
    df = pd.DataFrame(filtered)[["vendor", "term", "code"]]
    df.index = range(len(df))

    # Highlight selected row
    selected_idx = st.session_state.selected_idx
    if selected_idx >= len(filtered):
        selected_idx = 0
        st.session_state.selected_idx = 0

    # Show as a styled table with row selection
    selected_row = st.dataframe(
        df,
        use_container_width=True,
        height=500,
        on_select="rerun",
        selection_mode="single-row",
        key="queue_table"
    )

    # Update selection from click
    rows = selected_row.selection.get("rows", [])
    if rows:
        new_idx = rows[0]
        if new_idx != st.session_state.selected_idx:
            st.session_state.selected_idx = new_idx
            st.session_state.candidates   = []
            st.rerun()

    # Progress
    total_started = st.session_state.done_count + len(queue)
    if total_started > 0:
        st.progress(st.session_state.done_count / max(total_started, 1),
                    text=f"{st.session_state.done_count} done")

# ── RIGHT: Review panel ───────────────────────────────────────────────────────
with col_review:
    term_data = filtered[selected_idx]
    vendor_term = term_data["term"]
    vendor_name = term_data["vendor"]
    vendor_code = term_data["code"] or ""

    st.subheader("Review Term")

    # Term info card
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Vendor", vendor_name)
        c2.metric("Code",   vendor_code)
        c3.metric("Term",   vendor_term)

    # ── Vector search ──────────────────────────────────────────────────────
    search_col, _ = st.columns([1, 3])
    if search_col.button("🔍 Search OMOP Concepts", use_container_width=True):
        with st.spinner(f"Searching for '{vendor_term}'..."):
            try:
                candidates = search_concepts(
                    st.session_state.driver, neo4j_db,
                    vendor_term, openai_key
                )
                st.session_state.candidates = candidates
            except Exception as e:
                st.error(f"Search error: {e}")

    # ── Candidate cards ────────────────────────────────────────────────────
    if st.session_state.candidates:
        st.markdown("#### Top Concept Matches")

        for i, c in enumerate(st.session_state.candidates):
            score_pct = int(c.get("score", 0) * 100)
            score_color = (
                "🟢" if score_pct >= 80 else
                "🟡" if score_pct >= 60 else "🔴"
            )

            with st.expander(
                f"{score_color} **{c['concept_name']}** "
                f"— {c['domain']} / {c['vocabulary']} "
                f"— similarity: {score_pct}%",
                expanded=(i == 0)
            ):
                detail_c1, detail_c2 = st.columns(2)
                detail_c1.write(f"**Concept ID:** `{c['concept_id']}`")
                detail_c2.write(f"**Vocabulary:** {c['vocabulary']}")

                # Already mapped vendor terms
                if c.get("already_mapped"):
                    st.caption("**Other vendors mapped here:**")
                    for m in c["already_mapped"]:
                        if m.get("term"):
                            st.caption(f"  • {m.get('vendor', '?')} → {m['term']}")

                # Related concepts
                if c.get("related_concepts"):
                    rel_text = ", ".join(
                        f"{r['rel']} → {r['concept']}"
                        for r in c["related_concepts"] if r.get("concept")
                    )
                    if rel_text:
                        st.caption(f"**Graph context:** {rel_text}")

                # Action buttons
                btn1, btn2 = st.columns(2)

                if btn1.button(
                    "✅ Confirm (verified)",
                    key=f"confirm_{i}",
                    use_container_width=True,
                    type="primary"
                ):
                    try:
                        result = write_confirm(
                            st.session_state.driver, neo4j_db,
                            vendor_term, vendor_name,
                            c["concept_id"], curator
                        )
                        st.session_state.last_action = f"✅ Confirmed: **{vendor_term}** → {result['concept']}"
                        # Remove from queue
                        st.session_state.queue = [
                            t for t in st.session_state.queue
                            if not (t["term"] == vendor_term and t["vendor"] == vendor_name)
                        ]
                        st.session_state.done_count += 1
                        st.session_state.candidates = []
                        st.session_state.selected_idx = max(0, selected_idx - 1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Write error: {e}")

                if btn2.button(
                    "📋 Propose (needs review)",
                    key=f"propose_{i}",
                    use_container_width=True
                ):
                    try:
                        result = write_propose(
                            st.session_state.driver, neo4j_db,
                            vendor_term, vendor_name, vendor_code,
                            c["concept_id"], curator
                        )
                        st.session_state.last_action = f"📋 Proposed: **{vendor_term}** → {result['concept']}"
                        st.session_state.queue = [
                            t for t in st.session_state.queue
                            if not (t["term"] == vendor_term and t["vendor"] == vendor_name)
                        ]
                        st.session_state.done_count += 1
                        st.session_state.candidates = []
                        st.session_state.selected_idx = max(0, selected_idx - 1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Write error: {e}")

    # ── Skip button ────────────────────────────────────────────────────────
    st.divider()
    if st.button("⏭ Skip this term", use_container_width=False):
        try:
            write_skip(
                st.session_state.driver, neo4j_db,
                vendor_term, vendor_name, curator
            )
            st.session_state.last_action = f"⏭ Skipped: **{vendor_term}**"
            st.session_state.queue = [
                t for t in st.session_state.queue
                if not (t["term"] == vendor_term and t["vendor"] == vendor_name)
            ]
            st.session_state.done_count += 1
            st.session_state.candidates = []
            st.session_state.selected_idx = max(0, selected_idx - 1)
            st.rerun()
        except Exception as e:
            st.error(f"Skip error: {e}")

    # ── Last action feedback ───────────────────────────────────────────────
    if st.session_state.last_action:
        st.success(st.session_state.last_action)
