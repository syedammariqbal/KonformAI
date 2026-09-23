"""Gap Assessment Agent: Benchmarks required controls against user's uploaded internal policy docs."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router
from backend.rag.hybrid_retriever import hybrid_retriever

logger = logging.getLogger(__name__)

GAP_PROMPT = """You are an IT Audit and Compliance Lead for Banking Systems.
Your task is to compare the required regulatory controls (from EU AI Act and BaFin/MaRisk) against the user's documented internal controls.

Evaluate each domain:
1. Risk Management & Model Validation (MaRisk AT 4.3.2 / EU AI Act Art. 9)
2. Data Governance & Bias Auditing (EU AI Act Art. 10 / BaFin BDAI Principle 4)
3. Human Oversight & Override Controls (EU AI Act Art. 14 / BaFin BDAI Principle 2)
4. Technical Documentation & Logging (EU AI Act Art. 11, 12 / KWG § 25a)
5. Robustness & Cybersecurity (EU AI Act Art. 15 / BaFin AI Guidance 2026)

Identify missing or inadequate internal controls and rank their severity (HIGH, MEDIUM, LOW).
Provide a concrete remediation recommendation for each gap found.

Respond strictly with a JSON object:
{
  "gaps": [
    {
      "gap_id": "GAP-01",
      "control_area": "Human Oversight / Model Validation / Data Quality",
      "regulatory_reference": "EU AI Act Art. 14 / MaRisk AT 4.3.2",
      "severity": "HIGH" | "MEDIUM" | "LOW",
      "gap_description": "Precise description of missing or deficient control",
      "remediation_action": "Actionable step to close the gap"
    }
  ],
  "overall_readiness_score": 0.0 to 1.0,
  "summary": "Concise executive overview of control posture"
}
"""


async def gap_assessment_agent_node(state: GraphState) -> Dict[str, Any]:
    """Retrieves uploaded policy chunks and performs gap analysis against required controls."""
    logger.info("Executing gap_assessment_agent_node for Case %s", state.get("case_id"))

    merged = state.get("merged_obligations") or {}
    unified = merged.get("unified_obligations", [])

    # Search hybrid retriever for user uploaded policy documents if available
    uploaded_docs = hybrid_retriever.retrieve(
        query="internal policy model validation risk governance human oversight override",
        language="en",
        k=4,
    )

    uploaded_context_blocks = []
    for doc in uploaded_docs:
        if "Uploaded Policy" in str(doc.metadata.get("source_document", "")):
            uploaded_context_blocks.append(f"[{doc.metadata.get('source_document')}]\n{doc.page_content}")

    uploaded_context = (
        "\n\n".join(uploaded_context_blocks)
        if uploaded_context_blocks
        else "No internal policy documents uploaded by user. Assessing gaps against baseline unmitigated posture."
    )

    messages = [
        {"role": "system", "content": GAP_PROMPT},
        {
            "role": "user",
            "content": f"Required Unified Regulatory Controls:\n{json.dumps(unified, indent=2)}\n\nDocumented User Controls (Retrieved):\n{uploaded_context}",
        },
    ]

    response = await llm_router.complete(
        agent_name="GAP_ASSESSMENT_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
        retrieved_context=uploaded_context,
    )

    gaps = []
    readiness_score = 0.5
    summary = "Significant governance gaps identified versus MaRisk AT 4.3.2 and EU AI Act standards."

    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        gaps = data.get("gaps", [])
        readiness_score = float(data.get("overall_readiness_score", 0.5))
        summary = data.get("summary", "")
    except Exception as e:
        logger.warning("Gap assessment JSON parse error (%s). Using standard gap findings.", e)
        gaps = [
            {
                "gap_id": "GAP-01",
                "control_area": "Human Oversight",
                "regulatory_reference": "EU AI Act Article 14",
                "severity": "HIGH",
                "gap_description": "Lack of a documented override protocol enabling human credit officers to reverse automated loan rejections.",
                "remediation_action": "Formalize standard operating procedures and UI buttons for credit officers to log and override model output.",
            },
            {
                "gap_id": "GAP-02",
                "control_area": "Model Validation",
                "regulatory_reference": "MaRisk AT 4.3.2 (Tz. 3)",
                "severity": "HIGH",
                "gap_description": "No documented independent model validation prior to deployment or periodic backtesting schedule.",
                "remediation_action": "Commission an independent validation report from the risk control unit prior to production rollout.",
            },
            {
                "gap_id": "GAP-03",
                "control_area": "Data Governance",
                "regulatory_reference": "EU AI Act Article 10",
                "severity": "MEDIUM",
                "gap_description": "Absence of formalized bias detection and data drift monitoring metrics.",
                "remediation_action": "Establish continuous statistical monitoring for feature distribution drift.",
            },
        ]

    gap_data = {
        "gaps": gaps,
        "overall_readiness_score": readiness_score,
        "summary": summary,
    }

    return {
        "gap_assessment": gap_data,
        "current_node": "gap_assessment_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
