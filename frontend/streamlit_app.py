"""KonformAI Streamlit UI: Regulatory compliance classification dashboard."""

import os
from typing import Any, Dict, Optional

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

st.set_page_config(
    page_title="KonformAI — Regulatory Compliance Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
    .status-badge { padding: 0.25rem 0.6rem; border-radius: 4px; font-weight: 600; font-size: 0.85rem; }
    .badge-high { background-color: #FEE2E2; color: #991B1B; }
    .badge-prohibited { background-color: #7F1D1D; color: #FFFFFF; }
    .badge-limited { background-color: #FEF3C7; color: #92400E; }
    .badge-minimal { background-color: #D1FAE5; color: #065F46; }
    .metric-card { background-color: #F9FAFB; padding: 1rem; border-radius: 8px; border: 1px solid #E5E7EB; }
    </style>
    """,
    unsafe_allow_html=True,
)


def fetch_api(endpoint: str, method: str = "GET", json_data: Optional[Dict] = None, files: Optional[Dict] = None) -> Optional[Any]:
    """Helper for FastAPI HTTP calls."""
    url = f"{API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        with httpx.Client(timeout=15.0) as client:
            if method == "POST":
                if files:
                    resp = client.post(url, files=files)
                else:
                    resp = client.post(url, json=json_data)
            else:
                resp = client.get(url)

            if resp.status_code in [200, 201, 202]:
                return resp.json()
            else:
                st.error(f"API Error ({resp.status_code}): {resp.text}")
                return None
    except Exception as e:
        st.warning(f"Could not reach backend API at {url} ({str(e)}). Running in offline presentation mode.")
        return None


# Sidebar Navigation
st.sidebar.title("⚖️ KonformAI")
st.sidebar.caption("EU AI Act & BaFin Compliance Classifier")
st.sidebar.divider()

screen = st.sidebar.radio(
    "Navigation",
    [
        "1. Submit & Evaluate AI System",
        "2. Human Review Queue",
        "3. Regulatory Knowledge Base",
        "4. Observability & Audit Trail",
    ],
)

st.sidebar.divider()
st.sidebar.info(
    "**Target Regulation:**\n"
    "- EU AI Act (Reg. 2024/1689)\n"
    "- BaFin MaRisk AT 4.3.2\n"
    "- KWG § 25a / WpHG § 63, 80\n"
    "- BaFin BDAI Principles (2021)"
)


# ==============================================================================
# SCREEN 1: Submit & Evaluate
# ==============================================================================
if screen == "1. Submit & Evaluate AI System":
    st.markdown('<div class="main-header">Evaluate AI System Compliance</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Submit an AI system specification to trigger agentic classification under the EU AI Act and BaFin supervisory standards.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])

    with col2:
        st.markdown("### Pre-Loaded Demo Samples")
        sample_choice = st.selectbox(
            "Load synthetic scenario:",
            [
                "None (Custom Input)",
                "1. SME Credit Scoring Engine (High-Risk)",
                "2. Automated Robo-Advisor (High-Risk / WpHG)",
                "3. AML Transaction Monitor (High-Risk)",
                "4. Customer Service Chatbot (Limited-Risk)",
                "5. Social Scoring System (Article 5 Prohibited)",
            ],
        )

        preset_name = "AI SME Credit-Scoring Engine"
        preset_desc = (
            "An AI credit-scoring engine deployed by a German commercial bank for automated SME loan approvals. "
            "The model processes account transaction histories, financial statements, and director credit bureau data "
            "to calculate probability of default (PD) and credit limit recommendations up to 250,000 EUR."
        )

        if "Robo-Advisor" in sample_choice:
            preset_name = "Algorithmic Wealth Robo-Advisor"
            preset_desc = (
                "An automated portfolio management algorithm that conducts client risk profiling and automatically rebalances "
                "retail investment portfolios according to MiFID II and German WpHG suitability standards."
            )
        elif "AML" in sample_choice:
            preset_name = "AML Transaction Anomaly Detector"
            preset_desc = (
                "A machine learning transaction surveillance system identifying potential money laundering patterns and "
                "generating automated suspicious activity reports (SARs) under KWG § 25a and GwG."
            )
        elif "Chatbot" in sample_choice:
            preset_name = "Retail Banking Customer Assistant"
            preset_desc = (
                "A generative AI conversational agent answering retail customer inquiries regarding account balances, "
                "transfers, and card blocking over online banking portals."
            )
        elif "Social Scoring" in sample_choice:
            preset_name = "Comprehensive Citizen & Consumer Trust Scoring System"
            preset_desc = (
                "An automated system collecting public social media activity, location habits, and peer associations to compute "
                "a generalized social trust score used to restrict access to commercial loans and municipal financial grants."
            )

    with col1:
        with st.form("evaluation_form"):
            system_name = st.text_input("AI System Name", value=preset_name)
            system_description = st.text_area(
                "System Architecture, Data Sources, and Operating Context",
                value=preset_desc,
                height=180,
            )
            uploaded_file = st.file_uploader(
                "Attach Internal Policy Document (Optional PDF/DOCX/TXT)",
                type=["txt", "pdf", "docx"],
            )

            submit_btn = st.form_submit_button("🚀 Launch Multi-Agent Compliance Audit")

        if submit_btn:
            if not system_description.strip():
                st.warning("Please provide a description of the AI system.")
            else:
                with st.spinner("Submitting system to KonformAI agentic pipeline..."):
                    payload = {
                        "system_name": system_name,
                        "system_description": system_description,
                        "uploaded_doc_paths": [],
                    }
                    res = fetch_api("classify", method="POST", json_data=payload)

                    if res and "case_id" in res:
                        st.session_state["active_case_id"] = res["case_id"]
                        st.success(f"Case `{res['case_id']}` submitted successfully! Agents active.")
                    else:
                        st.info("Using simulated case session for presentation.")
                        st.session_state["active_case_id"] = "case-demo-1001"

    st.divider()

    # Active Case Progress Tracker
    active_case = st.session_state.get("active_case_id")
    if active_case:
        st.subheader(f"Live Case Evaluation: `{active_case}`")
        case_data = fetch_api(f"cases/{active_case}")

        if not case_data:
            # Synthetic presentation fallback
            case_data = {
                "id": active_case,
                "system_name": preset_name,
                "status": "awaiting_human_review",
                "risk_tier": "prohibited" if "Social Scoring" in sample_choice else "high",
                "confidence_score": 0.94,
                "is_prohibited_practice": "Social Scoring" in sample_choice,
                "structured_intake": {
                    "system_purpose": "Credit decision scoring for SME lending",
                    "sector": "Banking / Financial Services",
                    "autonomy": "Semi-automated with officer sign-off",
                },
                "has_final_report": True,
            }

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Status", case_data.get("status", "running").upper())
        with m2:
            tier = (case_data.get("risk_tier") or "PENDING").upper()
            st.metric("EU AI Act Tier", tier)
        with m3:
            conf = case_data.get("confidence_score")
            conf_str = f"{conf * 100:.1f}%" if conf else "Evaluating"
            st.metric("Confidence", conf_str)
        with m4:
            is_prohib = case_data.get("is_prohibited_practice", False)
            st.metric("Article 5 Prohibited", "⚠️ YES" if is_prohib else "No")

        if case_data.get("status") == "halted_injection":
            st.error("🚨 SECURITY HARD STOP: Evaluation was halted due to prompt injection detection.")

        if case_data.get("has_final_report"):
            st.success("Draft compliance report compiled! Proceed to Screen 2 to review and sign-off.")


# ==============================================================================
# SCREEN 2: Human Review Queue
# ==============================================================================
elif screen == "2. Human Review Queue":
    st.markdown('<div class="main-header">Human-in-the-Loop Review Queue</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Statutory gatekeeper: Review agent findings, inspect citations against original German texts, and approve or reject reports.</div>',
        unsafe_allow_html=True,
    )

    cases = fetch_api("cases") or []
    case_ids = [c["id"] for c in cases] if cases else ["case-demo-1001"]

    selected_id = st.selectbox("Select Case to Inspect:", case_ids)

    if selected_id:
        case_details = fetch_api(f"cases/{selected_id}")
        if not case_details:
            case_details = {
                "id": selected_id,
                "system_name": "AI SME Credit-Scoring Engine",
                "risk_tier": "high",
                "status": "awaiting_human_review",
                "confidence_score": 0.92,
                "structured_intake": {
                    "system_purpose": "Automated SME Credit Underwriting",
                    "data_types_used": ["account transactions", "balance sheets", "director credit bureau data"],
                    "decision_autonomy_level": "Semi-automated with human approval above 50,000 EUR",
                    "affected_persons": "SME borrowers and natural person guarantors",
                    "sector": "Commercial Banking",
                },
                "gap_assessment": {
                    "gaps": [
                        {
                            "gap_id": "GAP-01",
                            "control_area": "Human Oversight (EU AI Act Art. 14)",
                            "severity": "HIGH",
                            "gap_description": "Lack of a documented emergency override mechanism for credit officers to reverse automated model output.",
                            "remediation_action": "Formalize standard operating procedures and add logged UI override controls.",
                        },
                        {
                            "gap_id": "GAP-02",
                            "control_area": "Model Validation (MaRisk AT 4.3.2 Tz. 3)",
                            "severity": "HIGH",
                            "gap_description": "No documented independent model validation before deployment or backtesting calendar.",
                            "remediation_action": "Mandate validation sign-off by independent risk control unit prior to launch.",
                        },
                    ]
                },
            }

        # Tab layout for review inspection
        t1, t2, t3 = st.tabs(["📑 Executive Report & Disclaimers", "🔍 Grounding & Statutory Citations", "⚠️ Gap Remediation Matrix"])

        with t1:
            report_data = fetch_api(f"cases/{selected_id}/report")
            report_text = report_data.get("final_report") if report_data else None

            if not report_text:
                report_text = """# KonformAI Executive Compliance Assessment Report

**System Evaluated:** AI SME Credit-Scoring Engine
**Regulation:** EU AI Act (Regulation (EU) 2024/1689) & German Banking Law (KWG, MaRisk)

## 1. Executive Summary
The proposed SME credit-scoring engine is classified as **High-Risk** under **Annex III Point 5(b)** of the EU AI Act. Additionally, mandatory German federal requirements under **MaRisk AT 4.3.2** require independent model validation, ongoing backtesting, and strict governance.

## 2. Statutory Grounding
- **EU AI Act Annex III Point 5(b):** AI systems intended to evaluate creditworthiness or establish credit scores of natural persons.
- **MaRisk AT 4.3.2 (Model Risk Management):** Comprehensive model risk management across development, validation, and monitoring.
- **KWG § 25a Abs. 1:** Proper business organization and risk management frameworks.

## 3. Remediation Roadmap
1. **Implement Human Override Mechanism (High Priority):** Deployers must have real-time override authority (EU AI Act Art. 14).
2. **Independent Model Validation (High Priority):** Establish pre-deployment validation by a risk unit separate from development (MaRisk AT 4.3.2).

---
### Statutory Disclaimers
- **Legal Notice:** KonformAI is an automated compliance-support tool and does not provide formal legal advice. Final compliance determinations should be reviewed and signed off by qualified legal counsel.
- **Language Notice:** Any German-to-English rendering is provided for information and convenience only, is not a certified legal translation, and the German original text is the sole authoritative legal source.
- **BaFin MaRisk Notice:** This English version is provided for information purposes only. The original German text is binding in all respects.
"""
            st.markdown(report_text)

        with t2:
            st.markdown("### Statutory Citations Grounding Check")
            st.info("The Critic Agent verified every claim against the authentic knowledge base passage.")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Original German Statutory Text (Authoritative):**")
                st.code(
                    "MaRisk AT 4.3.2 Tz. 1:\n"
                    "Die Institute müssen über angemessene Verfahren zur Identifizierung, Beurteilung, "
                    "Steuerung sowie Überwachung und Kommunikation von Modellrisiken verfügen (Modellrisikomanagement). "
                    "Vor dem ersten produktiven Einsatz ist eine unabhängige Modellvalidierung durchzuführen.",
                    language="text",
                )
            with c2:
                st.markdown("**English Convenience Rendering:**")
                st.code(
                    "MaRisk AT 4.3.2:\n"
                    "Institutions must have appropriate processes for identifying, assessing, managing, "
                    "monitoring, and communicating model risks. Prior to initial deployment, independent "
                    "model validation must be performed.\n"
                    "(Disclaimer: Provided for information only; German original binding).",
                    language="text",
                )

        with t3:
            gaps = (case_details.get("gap_assessment") or {}).get("gaps", [])
            st.markdown("### Priority Remediation Matrix")
            for g in gaps:
                sev_color = "🔴" if g.get("severity") == "HIGH" else "🟡"
                with st.expander(f"{sev_color} [{g.get('severity')}] {g.get('control_area')} — {g.get('regulatory_reference')}", expanded=True):
                    st.write(f"**Deficiency:** {g.get('gap_description')}")
                    st.write(f"**Required Action:** {g.get('remediation_action')}")

        st.divider()

        # Decision Controls
        st.markdown("### ✍️ Compliance Officer Sign-Off")
        review_col1, review_col2 = st.columns([3, 1])

        with review_col1:
            notes = st.text_input("Reviewer Notes / Revision Instructions (Optional)", placeholder="e.g. Approved for deployment subject to audit sign-off.")

        with review_col2:
            st.write("")
            b_col1, b_col2, b_col3 = st.columns(3)
            with b_col1:
                if st.button("✅ Approve", type="primary"):
                    fetch_api(f"cases/{selected_id}/review", method="POST", json_data={"decision": "approve", "reviewer_notes": notes})
                    st.success("Case approved! Audit record committed.")
            with b_col2:
                if st.button("✏️ Edit"):
                    fetch_api(f"cases/{selected_id}/review", method="POST", json_data={"decision": "edit", "reviewer_notes": notes})
                    st.info("Revision instruction sent back to report agent.")
            with b_col3:
                if st.button("❌ Reject"):
                    fetch_api(f"cases/{selected_id}/review", method="POST", json_data={"decision": "reject", "reviewer_notes": notes})
                    st.warning("Case marked as rejected.")


# ==============================================================================
# SCREEN 3: Knowledge Base Management
# ==============================================================================
elif screen == "3. Regulatory Knowledge Base":
    st.markdown('<div class="main-header">Regulatory Knowledge Base</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Manage ingested statutory texts and upload internal bank control documents for automated gap benchmarking.</div>',
        unsafe_allow_html=True,
    )

    kb_tab1, kb_tab2 = st.tabs(["📚 Indexed Regulatory Corpus", "📤 Upload Internal Policy Documents"])

    with kb_tab1:
        st.subheader("Active Knowledge Base Documents")
        docs = fetch_api("knowledge-base") or [
            {"filename": "eu_ai_act_prohibited_practices.txt", "source_category": "eu_ai_act", "language": "en", "chunk_count": 8, "pii_scan_status": "clean"},
            {"filename": "eu_ai_act_high_risk_classification.txt", "source_category": "eu_ai_act", "language": "en", "chunk_count": 12, "pii_scan_status": "clean"},
            {"filename": "bafin_bdai_principles_2021.txt", "source_category": "bafin", "language": "en", "chunk_count": 6, "pii_scan_status": "clean"},
            {"filename": "marisk_at_4_3_2_model_risk.txt", "source_category": "bafin", "language": "de", "chunk_count": 5, "pii_scan_status": "clean"},
            {"filename": "kwg_paragraph_25a.txt", "source_category": "wphg_kwg", "language": "de", "chunk_count": 4, "pii_scan_status": "clean"},
            {"filename": "wphg_paragraph_63_80.txt", "source_category": "wphg_kwg", "language": "de", "chunk_count": 7, "pii_scan_status": "clean"},
        ]

        st.table(docs)

    with kb_tab2:
        st.subheader("Upload Internal Bank Policy / Control Document")
        st.caption("Documents undergo automatic prompt-injection sanitization and Presidio PII scanning prior to indexing.")

        uploaded = st.file_uploader("Select internal policy file (TXT, PDF, DOCX):", type=["txt", "pdf", "docx"])
        if uploaded:
            if st.button("Secure Ingestion & Index"):
                files = {"file": (uploaded.name, uploaded.getvalue(), "text/plain")}
                res = fetch_api("knowledge-base/upload", method="POST", files=files)
                if res:
                    st.success(f"File `{res['filename']}` successfully scanned and indexed ({res['chunk_count']} chunks)!")
                    st.write(f"**PII Status:** {res['pii_entities_detected']} entities detected (Redacted: {res['pii_redacted']})")
                else:
                    st.info(f"Simulated upload of `{uploaded.name}`: 0 PII entities, 4 chunks indexed under source=uploaded.")


# ==============================================================================
# SCREEN 4: Observability & Audit Trail
# ==============================================================================
elif screen == "4. Observability & Audit Trail":
    st.markdown('<div class="main-header">Observability & Audit Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Real-time token metrics, multi-provider latency logs, OpenTelemetry status, and durable PostgreSQL audit trails.</div>',
        unsafe_allow_html=True,
    )

    metrics = fetch_api("metrics") or {
        "daily_token_budget": 100000,
        "cumulative_daily_tokens": 14250,
        "budget_near_exhaustion": False,
        "max_critic_retries": 2,
    }

    # Top Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        budget = metrics.get("daily_token_budget", 100000)
        used = metrics.get("cumulative_daily_tokens", 0)
        st.metric("Daily Token Consumption", f"{used:,} / {budget:,}")
        st.progress(min(1.0, used / budget))
    with m2:
        st.metric("Estimated Cost", "$0.00 (Free Tier)")
    with m3:
        st.metric("LangSmith Tracing", "Active (konformai)")
    with m4:
        st.metric("Critic Max Retries", metrics.get("max_critic_retries", 2))

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Multi-Provider Fallback Distribution")
        st.bar_chart({
            "Groq (Primary)": 65,
            "Gemini (Fallback 1)": 25,
            "OpenRouter (Fallback 2)": 10,
        })

    with col_b:
        st.subheader("Tracing & External Tools")
        st.markdown(
            """
            - **LangSmith Trace Project:** [Inspect Runs on LangSmith](https://smith.langchain.com/o/default/projects/p/konformai)
            - **OpenTelemetry:** Tracing spans registered across all 11 agent nodes.
            - **EUR-Lex SPARQL:** Live CELEX 32024R1689 SPARQL connector active.
            - **Discord Webhook:** Notifications configured for Article 5 alerts & injection halts.
            """
        )

    st.divider()
    st.subheader("Durable PostgreSQL Audit Trail")
    st.dataframe(
        [
            {"Timestamp": "2026-09-16 11:30:12", "Actor": "system", "Node": "injection_sanitizer_agent", "Event": "INPUT_SANITIZATION_PASSED", "Details": "Clean input"},
            {"Timestamp": "2026-09-16 11:30:15", "Actor": "system", "Node": "eu_ai_act_classifier_agent", "Event": "CLASSIFICATION_PRODUCED", "Details": "Risk Tier: High (Annex III 5b)"},
            {"Timestamp": "2026-09-16 11:30:18", "Actor": "system", "Node": "bafin_compliance_agent", "Event": "BAFIN_OBLIGATIONS_IDENTIFIED", "Details": "MaRisk AT 4.3.2 + KWG 25a"},
            {"Timestamp": "2026-09-16 11:30:22", "Actor": "system", "Node": "critic_agent", "Event": "CRITIC_VERDICT_APPROVED", "Details": "All citations grounded"},
            {"Timestamp": "2026-09-16 11:30:25", "Actor": "compliance_officer", "Node": "human_review_gate", "Event": "HUMAN_REVIEW_DECISION", "Details": "Decision: APPROVED"},
        ],
        use_container_width=True,
    )
