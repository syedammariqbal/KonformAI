"""Intake Agent: Normalizes free-text or structured system descriptions."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState, StructuredIntake
from backend.llm_router.router import llm_router

logger = logging.getLogger(__name__)

INTAKE_PROMPT = """You are a Senior Regulatory Compliance Analyst specializing in the German financial sector.
Your task is to analyze the user's description of an AI system and extract a structured technical and operational profile.

Respond with a valid JSON object containing exactly these fields:
{
  "system_purpose": "Clear summary of the system's objective and core functionality",
  "data_types_used": ["List", "of", "input", "data", "categories"],
  "decision_autonomy_level": "e.g., fully automated, decision-support with human approval, advisory only",
  "affected_persons": "Categories of natural or legal persons affected (e.g., loan applicants, SME owners)",
  "deployment_context": "Deployment setting (e.g., credit underwriting, trading desk, fraud prevention in Germany)",
  "sector": "Banking / Financial Services / Insurance"
}

Do not include any conversational filler. Return ONLY the JSON object.
"""


async def intake_agent_node(state: GraphState) -> Dict[str, Any]:
    """Parses and normalizes the input system description into StructuredIntake."""
    logger.info("Executing intake_agent_node for Case %s", state.get("case_id"))

    description = state.get("system_description", "")
    clarification_info = ""
    if state.get("clarification_responses"):
        clarification_info = "\n\nAdditional Clarification Provided:\n" + "\n".join(state["clarification_responses"])

    messages = [
        {"role": "system", "content": INTAKE_PROMPT},
        {"role": "user", "content": f"AI System Description:\n{description}{clarification_info}"},
    ]

    response = await llm_router.complete(
        agent_name="INTAKE_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
    )

    try:
        cleaned_content = response.content.strip()
        if "```json" in cleaned_content:
            cleaned_content = cleaned_content.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_content:
            cleaned_content = cleaned_content.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned_content)
        structured_intake = StructuredIntake(**data).model_dump()
    except Exception as e:
        logger.warning("Intake JSON parsing error (%s). Using fallback structured intake.", e)
        structured_intake = StructuredIntake(
            system_purpose=description[:200],
            data_types_used=["financial records", "transaction history"],
            decision_autonomy_level="semi-automated with human approval",
            affected_persons="banking customers",
            deployment_context="German financial institution",
            sector="Banking / Financial Services",
        ).model_dump()

    return {
        "structured_intake": structured_intake,
        "current_node": "intake_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
