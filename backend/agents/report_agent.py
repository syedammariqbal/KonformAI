"""Report Agent: Synthesizes approved findings into a formal compliance report and roadmap."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router

logger = logging.getLogger(__name__)

REPORT_PROMPT = """You are a Senior Regulatory Compliance Officer at a Tier-1 German Bank.
Draft a professional, authoritative, and actionable Compliance Classification Report and Remediation Roadmap.

Report Structure Required:
1. Executive Summary & AI System Profile (System Name, Purpose, Autonomy Level, Deployment Context)
2. EU AI Act Classification & Legal Analysis (Risk Tier, Specific Articles & Annexes cited, mandatory legal requirements)
3. German BaFin & Federal Supervisory Requirements (MaRisk AT 4.3.2 Model Risk Management, KWG § 25a, BaFin BDAI 2021)
4. Gap Assessment & Prioritized Remediation Roadmap (Actionable matrix of gaps ranked by High/Medium/Low severity with concrete implementation steps)
5. Legal Notice & Translation Disclaimers

Mandatory Legal Disclaimers to Include Verbatim:
- "Disclaimer: KonformAI is an automated compliance-support tool and does not provide formal legal advice. Final compliance determinations should be reviewed and signed off by qualified legal counsel."
- "German Translation Notice: Any German-to-English rendering is provided for information and convenience only, is not a certified legal translation, and the German original text is the sole authoritative legal source."
- If MaRisk is cited: "BaFin MaRisk Notice: This English version is provided for information purposes only. The original German text is binding in all respects."

Write the report in clear, structured Markdown suitable for executive submission to the Management Board.
"""


async def report_agent_node(state: GraphState) -> Dict[str, Any]:
    """Compiles all verified compliance outputs into an executive-ready Markdown report."""
    logger.info("Executing report_agent_node for Case %s", state.get("case_id"))

    intake = state.get("structured_intake") or {}
    eu_data = state.get("eu_ai_act_classification") or {}
    bafin_data = state.get("bafin_obligations") or {}
    merged = state.get("merged_obligations") or {}
    gaps = state.get("gap_assessment") or {}
    translations = state.get("translated_passages") or []

    synthesis_input = {
        "system_profile": intake,
        "eu_ai_act_classification": eu_data,
        "bafin_obligations": bafin_data,
        "unified_obligations": merged,
        "gap_analysis": gaps,
        "translated_statutory_sources": translations,
    }

    messages = [
        {"role": "system", "content": REPORT_PROMPT},
        {"role": "user", "content": f"Verified Compliance Package:\n{json.dumps(synthesis_input, indent=2)}"},
    ]

    response = await llm_router.complete(
        agent_name="REPORT_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
    )

    final_report = response.content.strip()

    # Ensure disclaimer is present even if model trimmed it
    if "Disclaimer: KonformAI is an automated compliance-support tool" not in final_report:
        final_report += (
            "\n\n---\n"
            "### Statutory Disclaimers\n"
            "- **Legal Notice:** KonformAI is an automated compliance-support tool and does not provide formal legal advice. "
            "Final compliance determinations should be reviewed and signed off by qualified legal counsel.\n"
            "- **Language Notice:** Any German-to-English rendering is provided for information and convenience only, is not a certified "
            "legal translation, and the German original text is the sole authoritative legal source.\n"
            "- **BaFin MaRisk Notice:** This English version is provided for information purposes only. The original German text is binding in all respects.\n"
        )

    logger.info("Compliance report drafted successfully (%d characters).", len(final_report))

    return {
        "final_report": final_report,
        "human_review_required": True,
        "graph_status": "awaiting_human_review",
        "current_node": "report_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
