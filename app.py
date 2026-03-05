"""
OMOP Mapping Curation Queue — local Streamlit app
Run: streamlit run app.py
"""
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from neo4j_utils import (
    get_driver, get_unmapped_terms, get_proposed_mappings,
    search_concepts, search_vendor_terms,
    write_propose, write_confirm, write_promote, write_reject, write_skip
)

load_dotenv()

st.set_page_config(page_title="OMOP Curation Queue", page_icon="🧬", layout="wide")
st.title("🧬 OMOP Mapping Curation Queue")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Connection")
    neo4j_uri  = st.text_input("Neo4j URI",     value=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_db   = st.text_input("Database",       value=os.getenv("NEO4J_DATABASE", "neo4j"))
    neo4j_user = st.text_input("Username",       value=os.getenv("NEO4J_USERNAME", "neo4j"))
    neo4j_pass = st.text_input("Password",       value=os.getenv("NEO4J_PASSWORD", ""), type="password")
    openai_key = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    curator    = st.text_input("Your name",      value="curator_1",
                               help="Written into the audit trail on every mapping")
    st.divider()
    connect_btn = st.button("🔌 Connect & Load Queue", use_container_width=True)
    st.divider()
    st.caption("**Search settings**")
    confidence_threshold = st.slider(
        "Min. similarity threshold", min_value=0, max_value=100,
        value=60, step=5, format="%d%%",
        help="Hide candidates below this similarity score"
    )
    st.divider()
    st.caption("P = Propose  |  C = Confirm  |  S = Skip")

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "driver": None, "queue": [], "proposed": [],
    "selected_idx": 0, "candidates": [], "vendor_matches": [],
    "search_mode": None, "last_action": None, "done_count": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Helper ────────────────────────────────────────────────────────────────────
def remove_from_queue(vendor_term_id):
    st.session_state.queue = [
        t for t in st.session_state.queue
        if t["vendor_term_id"] != vendor_term_id
    ]
    st.session_state.done_count    += 1
    st.session_state.candidates     = []
    st.session_state.vendor_matches = []
    st.session_state.selected_idx   = max(0, st.session_state.selected_idx - 1)

# ── Connect ───────────────────────────────────────────────────────────────────
if connect_btn:
    try:
        driver = get_driver(neo4j_uri, neo4j_user, neo4j_pass)
        driver.verify_connectivity()
        st.session_state.driver   = driver
        st.session_state.queue    = get_unmapped_terms(driver, neo4j_db)
        st.session_state.proposed = get_proposed_mappings(driver, neo4j_db)
        st.session_state.selected_idx = 0
        st.sidebar.success(
            f"✅ Connected — {len(st.session_state.queue)} unmapped, "
            f"{len(st.session_state.proposed)} proposed"
        )
    except Exception as e:
        st.sidebar.error(f"Connection failed: {e}")

if not st.session_state.driver:
    st.info("👈 Enter your Neo4j credentials in the sidebar and click **Connect & Load Queue**.")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_queue, tab_proposed = st.tabs([
    f"📋 Unmapped Queue ({len(st.session_state.queue)})",
    f"🔎 Proposed Review ({len(st.session_state.proposed)})",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Unmapped Queue
# ══════════════════════════════════════════════════════════════════════════════
with tab_queue:
    queue = st.session_state.queue
    if not queue:
        st.success("🎉 No unmapped terms remaining!")
    else:
        col_queue, col_review = st.columns([1, 2], gap="large")

        with col_queue:
            st.subheader(f"Queue ({len(queue)} remaining)")
            vendors = sorted(set(t["vendor"] for t in queue))
            vendor_filter = st.multiselect("Filter by vendor", vendors, default=vendors, key="vf")
            filtered = [t for t in queue if t["vendor"] in vendor_filter]

            if not filtered:
                st.warning("No terms match the filter.")
            else:
                df = pd.DataFrame(filtered)[["vendor", "term", "code"]]
                df.index = range(len(df))

                selected_idx = st.session_state.selected_idx
                if selected_idx >= len(filtered):
                    selected_idx = 0
                    st.session_state.selected_idx = 0

                selected_row = st.dataframe(
                    df, use_container_width=True, height=460,
                    on_select="rerun", selection_mode="single-row",
                    key="queue_table"
                )
                rows = selected_row.selection.get("rows", [])
                if rows and rows[0] != st.session_state.selected_idx:
                    st.session_state.selected_idx   = rows[0]
                    st.session_state.candidates     = []
                    st.session_state.vendor_matches = []
                    st.session_state.search_mode    = None
                    st.rerun()

                total = st.session_state.done_count + len(queue)
                if total > 0:
                    st.progress(st.session_state.done_count / max(total, 1),
                                text=f"{st.session_state.done_count} done")

        with col_review:
            if filtered:
                term_data      = filtered[selected_idx]
                vendor_term_id = term_data["vendor_term_id"]
                vendor_term    = term_data["term"]
                vendor_name    = term_data["vendor"]
                vendor_code    = term_data["code"] or ""

                st.subheader("Review Term")
                with st.container(border=True):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Vendor", vendor_name)
                    c2.metric("Code",   vendor_code)
                    c3.metric("Term",   vendor_term)

                btn_concept, btn_vendor = st.columns(2)
                if btn_concept.button("🔍 Search OMOP Concepts", use_container_width=True):
                    with st.spinner(f"Searching concepts for '{vendor_term}'..."):
                        try:
                            st.session_state.candidates     = search_concepts(
                                st.session_state.driver, neo4j_db, vendor_term_id, openai_key)
                            st.session_state.vendor_matches = []
                            st.session_state.search_mode    = "concept"
                        except Exception as e:
                            st.error(f"Search error: {e}")

                if btn_vendor.button("🔗 Search Similar Vendor Terms", use_container_width=True):
                    with st.spinner(f"Finding similar vendor terms for '{vendor_term}'..."):
                        try:
                            st.session_state.vendor_matches = search_vendor_terms(
                                st.session_state.driver, neo4j_db, vendor_term_id, openai_key)
                            st.session_state.candidates     = []
                            st.session_state.search_mode    = "vendor"
                        except Exception as e:
                            st.error(f"Search error: {e}")

                if st.session_state.search_mode:
                    st.caption(f"Showing results ≥ {confidence_threshold}% · adjust in sidebar")

                # ── OMOP concept results ──────────────────────────────────
                if st.session_state.candidates:
                    visible = [c for c in st.session_state.candidates
                               if int(c.get("score", 0) * 100) >= confidence_threshold]
                    hidden  = len(st.session_state.candidates) - len(visible)
                    st.markdown("#### Top OMOP Concept Matches")
                    if hidden:
                        st.caption(f"*{hidden} result(s) hidden below {confidence_threshold}%*")
                    if not visible:
                        st.warning("No results above threshold. Lower the slider in the sidebar.")
                    for i, c in enumerate(visible):
                        score_pct   = int(c.get("score", 0) * 100)
                        score_color = "🟢" if score_pct >= 80 else "🟡" if score_pct >= 60 else "🔴"
                        with st.expander(
                            f"{score_color} **{c['concept_name']}** — {c['domain']} / {c['vocabulary']} — {score_pct}%",
                            expanded=(i == 0)
                        ):
                            d1, d2 = st.columns(2)
                            d1.write(f"**Concept ID:** `{c['concept_id']}`")
                            d2.write(f"**Vocabulary:** {c['vocabulary']}")
                            if c.get("already_mapped"):
                                st.caption("**Other vendors mapped here:**")
                                for m in c["already_mapped"]:
                                    if m.get("term"):
                                        st.caption(f"  • {m.get('vendor','?')} → {m['term']}")
                            if c.get("related_concepts"):
                                rel_text = ", ".join(
                                    f"{r['rel']} → {r['concept']}"
                                    for r in c["related_concepts"] if r.get("concept")
                                )
                                if rel_text:
                                    st.caption(f"**Graph context:** {rel_text}")
                            b1, b2 = st.columns(2)
                            if b1.button("✅ Confirm (verified)", key=f"confirm_{i}",
                                         use_container_width=True, type="primary"):
                                try:
                                    result = write_confirm(st.session_state.driver, neo4j_db,
                                                           vendor_term_id, c["concept_id"], curator)
                                    st.session_state.last_action = f"✅ Confirmed: **{vendor_term}** → {result['concept']}"
                                    remove_from_queue(vendor_term_id)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Write error: {e}")
                            if b2.button("📋 Propose (needs review)", key=f"propose_{i}",
                                         use_container_width=True):
                                try:
                                    result = write_propose(st.session_state.driver, neo4j_db,
                                                           vendor_term_id, c["concept_id"], curator)
                                    st.session_state.last_action = f"📋 Proposed: **{vendor_term}** → {result['concept']}"
                                    remove_from_queue(vendor_term_id)
                                    st.session_state.proposed = get_proposed_mappings(
                                        st.session_state.driver, neo4j_db)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Write error: {e}")

                # ── Vendor term results ───────────────────────────────────
                if st.session_state.vendor_matches:
                    visible = [m for m in st.session_state.vendor_matches
                               if int(m.get("score", 0) * 100) >= confidence_threshold]
                    hidden  = len(st.session_state.vendor_matches) - len(visible)
                    st.markdown("#### Similar Vendor Terms (Already Mapped)")
                    st.caption("Adopt the same concept as a similar term from another vendor.")
                    if hidden:
                        st.caption(f"*{hidden} result(s) hidden below {confidence_threshold}%*")
                    if not visible:
                        st.warning("No results above threshold. Lower the slider in the sidebar.")
                    for i, m in enumerate(visible):
                        score_pct   = int(m.get("score", 0) * 100)
                        score_color = "🟢" if score_pct >= 80 else "🟡" if score_pct >= 60 else "🔴"
                        with st.expander(
                            f"{score_color} **{m['vendor_term']}** ({m['vendor']}) → {m['concept_name']} — {score_pct}%",
                            expanded=(i == 0)
                        ):
                            c1, c2, c3 = st.columns(3)
                            c1.write(f"**Concept ID:** `{m['concept_id']}`")
                            c2.write(f"**Domain:** {m['domain']}")
                            c3.write(f"**Vocabulary:** {m['vocabulary']}")
                            st.caption(f"*{m['vendor']}* `{m['vendor_code']}` → already mapped to **{m['concept_name']}**")
                            ba, bb = st.columns(2)
                            if ba.button("✅ Confirm same mapping", key=f"vconfirm_{i}",
                                         use_container_width=True, type="primary"):
                                try:
                                    result = write_confirm(st.session_state.driver, neo4j_db,
                                                           vendor_term_id, m["concept_id"], curator)
                                    st.session_state.last_action = (
                                        f"✅ Confirmed: **{vendor_term}** → {result['concept']} "
                                        f"(from {m['vendor']}: {m['vendor_term']})")
                                    remove_from_queue(vendor_term_id)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Write error: {e}")
                            if bb.button("📋 Propose same mapping", key=f"vpropose_{i}",
                                         use_container_width=True):
                                try:
                                    result = write_propose(st.session_state.driver, neo4j_db,
                                                           vendor_term_id, m["concept_id"], curator)
                                    st.session_state.last_action = (
                                        f"📋 Proposed: **{vendor_term}** → {result['concept']} "
                                        f"(from {m['vendor']}: {m['vendor_term']})")
                                    remove_from_queue(vendor_term_id)
                                    st.session_state.proposed = get_proposed_mappings(
                                        st.session_state.driver, neo4j_db)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Write error: {e}")

                st.divider()
                if st.button("⏭ Skip this term"):
                    try:
                        write_skip(st.session_state.driver, neo4j_db,
                                   vendor_term_id, curator)
                        st.session_state.last_action = f"⏭ Skipped: **{vendor_term}**"
                        remove_from_queue(vendor_term_id)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Skip error: {e}")

                if st.session_state.last_action:
                    st.success(st.session_state.last_action)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Proposed Review
# ══════════════════════════════════════════════════════════════════════════════
with tab_proposed:
    proposed = st.session_state.proposed

    col_h1, col_h2 = st.columns([3, 1])
    col_h1.subheader(f"Proposed Mappings Awaiting Sign-off ({len(proposed)})")
    if col_h2.button("🔄 Refresh", use_container_width=True, key="refresh_proposed"):
        st.session_state.proposed = get_proposed_mappings(st.session_state.driver, neo4j_db)
        st.rerun()

    if not proposed:
        st.info("No proposed mappings waiting for review.")
    else:
        f1, f2 = st.columns(2)
        p_vendors    = sorted(set(p["vendor"] for p in proposed))
        p_by         = sorted(set(p["proposed_by"] for p in proposed if p["proposed_by"]))
        p_filter     = f1.multiselect("Filter by vendor",   p_vendors, default=p_vendors, key="pf")
        p_by_filter  = f2.multiselect("Filter by proposer", p_by,      default=p_by,      key="pbf")

        filtered_p = [p for p in proposed
                      if p["vendor"] in p_filter and p["proposed_by"] in p_by_filter]

        st.caption(f"Showing {len(filtered_p)} of {len(proposed)}")
        st.divider()

        for idx, p in enumerate(filtered_p):
            with st.container(border=True):
                h1, h2, h3, h4 = st.columns([2, 2, 2, 1])
                h1.markdown(f"**{p['vendor']}** `{p['code']}`")
                h2.markdown(f"📝 {p['term']}")
                h3.markdown(f"→ **{p['concept_name']}**  \n`{p['concept_id']}` · {p['domain']} / {p['vocabulary']}")
                h4.caption(f"by *{p['proposed_by']}*  \n{p['proposed_at'][:16] if p['proposed_at'] else ''}")

                a1, a2 = st.columns(2)
                if a1.button("✅ Approve → Verified", key=f"promote_{idx}",
                             use_container_width=True, type="primary"):
                    try:
                        write_promote(st.session_state.driver, neo4j_db,
                                      p["vendor_term_id"], p["concept_id"], curator)
                        st.session_state.proposed = get_proposed_mappings(
                            st.session_state.driver, neo4j_db)
                        st.session_state.last_action = f"✅ Approved: **{p['term']}** → {p['concept_name']}"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Approve error: {e}")

                reject_key = f"reject_open_{idx}"
                if reject_key not in st.session_state:
                    st.session_state[reject_key] = False

                if a2.button("❌ Reject", key=f"reject_btn_{idx}", use_container_width=True):
                    st.session_state[reject_key] = not st.session_state[reject_key]
                    st.rerun()

                if st.session_state[reject_key]:
                    reason = st.text_input("Rejection reason", key=f"reason_{idx}",
                                           placeholder="e.g. Wrong domain, too generic...")
                    if st.button("Confirm rejection", key=f"reject_confirm_{idx}"):
                        if not reason.strip():
                            st.warning("Please enter a reason.")
                        else:
                            try:
                                write_reject(st.session_state.driver, neo4j_db,
                                             p["vendor_term_id"], p["concept_id"],
                                             curator, reason)
                                st.session_state.proposed = get_proposed_mappings(
                                    st.session_state.driver, neo4j_db)
                                st.session_state[reject_key] = False
                                st.session_state.last_action = f"❌ Rejected: **{p['term']}** — {reason}"
                                st.rerun()
                            except Exception as e:
                                st.error(f"Reject error: {e}")

        if st.session_state.last_action:
            st.success(st.session_state.last_action)
