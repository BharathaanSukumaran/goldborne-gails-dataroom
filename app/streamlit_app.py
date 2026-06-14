from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dataroom_pipeline.assistant import answer_question
from dataroom_pipeline.llm_client import provider_status
from dataroom_pipeline.paths import DB_PATH, REPORTS_DIR
from dataroom_pipeline.pipeline import run_pipeline
from dataroom_pipeline.storage import connect, rows


st.set_page_config(page_title="Gail's Dataroom", layout="wide")


def ensure_data() -> None:
    if not DB_PATH.exists():
        run_pipeline()


def load_summary() -> dict:
    path = REPORTS_DIR / "app_summary.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


ensure_data()
summary = load_summary()

st.title("Gail's Limited Dataroom")
st.caption("Pipeline-first dataroom workspace with structured facts, provenance, and assistant UI.")

top = st.columns(4)
top[0].metric("Company", summary.get("company", {}).get("company_number", "06055393"))
top[1].metric("Documents", summary.get("document_count", 0))
top[2].metric("Processed", summary.get("processed_document_count", 0))
top[3].metric("Open QA items", summary.get("open_issue_count", 0))

llm_status = provider_status()
with st.expander("Assistant runtime", expanded=False):
    st.write(llm_status["reason"])
    st.json({
        "provider": llm_status["provider"],
        "model": llm_status["model"],
        "enabled": llm_status["enabled"],
        "ready": llm_status["ready"],
        "free_local_option": "Set LLM_PROVIDER=ollama and ASSISTANT_USE_LLM=true with a local Ollama model.",
    })

conn = connect(DB_PATH)

overview_tab, pipeline_tab, assistant_tab, documents_tab = st.tabs(
    ["Overview", "Pipeline", "Assistant", "Documents"]
)

with overview_tab:
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Company")
        companies = rows(conn, "SELECT * FROM companies")
        st.dataframe(companies, use_container_width=True)

        st.subheader("Ownership")
        st.dataframe(rows(conn, "SELECT owner_name, control_type, percentage_band, status FROM ownership"), use_container_width=True)

    with right:
        st.subheader("Charges")
        st.dataframe(rows(conn, "SELECT charge_code, created_date, status, holder FROM charges"), use_container_width=True)

        st.subheader("Financial Facts")
        st.dataframe(rows(conn, "SELECT metric, value, unit, period_end, confidence, note FROM financial_facts"), use_container_width=True)

with pipeline_tab:
    st.subheader("Pipeline Run")
    st.json(summary)

    st.subheader("Validation Findings")
    findings = rows(conn, "SELECT severity, finding, status, document_id FROM qa_findings ORDER BY severity")
    st.dataframe(findings, use_container_width=True)

    st.subheader("Canonical Tables")
    table = st.selectbox(
        "Inspect table",
        ["documents", "financial_facts", "charges", "officers", "ownership", "events", "qa_findings"],
    )
    st.dataframe(rows(conn, f"SELECT * FROM {table}"), use_container_width=True)

with assistant_tab:
    st.subheader("Assistant")
    examples = [
        "What was revenue and EBITDA in the last reported year?",
        "What charges are registered against the company and who holds them?",
        "What are the key risks for a lender?",
        "Draft a short credit summary of the business.",
    ]
    selected = st.selectbox("Sample questions", examples)
    question = st.chat_input("Ask a question about the dataroom")
    if st.button("Run sample question"):
        question = selected

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        result = answer_question(question)
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            st.markdown(result["answer"])
            st.caption(f"Route: {result['route']}")
            if result["citations"]:
                st.write("Sources")
                for citation in result["citations"]:
                    st.link_button(citation["title"], citation["url"])
        st.session_state.messages.append({"role": "assistant", "content": result["answer"]})

with documents_tab:
    st.subheader("Dataroom Inventory")
    docs = rows(
        conn,
        """
        SELECT document_id, title, category, source, document_date, reporting_period_end,
               inbox_file, processed_path, source_url
        FROM documents
        ORDER BY category, document_date DESC
        """,
    )
    st.dataframe(docs, use_container_width=True)

conn.close()
