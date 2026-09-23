"""Conflict Resolution Agent: Harmonizes EU AI Act and BaFin/German obligations."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router

logger = logging.getLogger(__name__)

CONFLICT_PROMPT = """You are a Financial Regulatory Harmonization Director.
Your task is to merge the EU AI Act classification and obligations with German national supervisory requirements (BaFin, MaRisk, KWG).

Harmonization Guidelines:
1. EU AI Act sets the horizontal baseline across the single market.
2. BaFin requirements (especially MaRisk AT 4.3.2 Model Risk Management) set stringent sectoral supervisory expectations for credit and risk models.
3. Identify where German rules impose stricter or more specific mandates than EU rules (e.g., formal independent model validation unit, backtesting calendars).
4. Flag any friction points or cumulative compliance burdens.

Respond strictly with a JSON object:
{
  "unified_obligations": [
    {
      "control_domain": "Risk Management / Model Governance / Human Oversight / Data Quality",
      "eu_requirement": "Summary of EU AI Act mandate",
      "german_supervisory_requirement": "Summary of BaFin / MaRisk / KWG mandate",
      "synthesis": "Harmonized requirement for the institution",
      "strictest_rule": "EU or BaFin",
      "relevant_citations": ["Article 9", "MaRisk AT 4.3.2"]
    }
  ],
  "conflicts_or_overlaps": [
    "List of specific overlaps or coordination challenges identified"
  ]
}
"""


async def conflict_resolution_agent_node(state: GraphState) -> Dict[str, Any]:
    """Merges EU AI Act and BaFin obligations into a unified compliance baseline."""
    logger.info("Executing conflict_resolution_agent_node for Case %s", state.get("case_id"))

    eu_data = state.get("eu_ai_act_classification") or {}
    bafin_data = state.get("bafin_obligations") or {}
    translations = state.get("translated_passages") or []

    combined_input = {
        "eu_classification": eu_data,
        "bafin_obligations": bafin_data,
        "translated_german_sources": translations,
    }

    messages = [
        {"role": "system", "content": CONFLICT_PROMPT},
        {"role": "user", "content": f"Regulatory Findings to Harmonize:\n{json.dumps(combined_input, indent=2)}"},
    ]

    response = await llm_router.complete(
        agent_name="CONFLICT_RESOLUTION_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
    )

    unified = []
    conflicts = []
    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        unified = data.get("unified_obligations", [])
        conflicts = data.get("conflicts_or_overlaps", [])
    except Exception as e:
        logger.warning("Conflict resolution JSON parse error (%s). Using fallback synthesis.", e)
        unified = [
            {
                "control_domain": "Model Risk & Governance",
                "eu_requirement": "Risk management system throughout AI lifecycle (EU AI Act Article 9)",
                "german_supervisory_requirement": "Independent model validation and ongoing backtesting (MaRisk AT 4.3.2)",
                "synthesis": "Establish lifecycle model governance with independent risk control sign-off.",
                "strictest_rule": "BaFin (MaRisk AT 4.3.2)",
                "relevant_citations": ["EU AI Act Article 9", "MaRisk AT 4.3.2"],
            },
            {
                "control_domain": "Human Oversight",
                "eu_requirement": "Deployer override and stop capabilities (EU AI Act Article 14)",
                "german_supervisory_requirement": "Management board responsibility and manual escalation (BaFin BDAI Principle 2)",
                "synthesis": "Implement human intervention interfaces with logged override decisions.",
                "strictest_rule": "Cumulative",
                "relevant_citations": ["EU AI Act Article 14", "BaFin BDAI Principle 2"],
            },
        ]
        conflicts = ["BaFin requires organizational independence of model validation which exceeds general EU AI Act Article 9 text."]

    merged_obligations = {
        "unified_obligations": unified,
        "conflicts_or_overlaps": conflicts,
    }

    return {
        "merged_obligations": merged_obligations,
        "current_node": "conflict_resolution_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
