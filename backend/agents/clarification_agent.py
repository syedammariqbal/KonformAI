"""Clarification Agent: Generates targeted inquiries when classification confidence is low."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router

logger = logging.getLogger(__name__)

CLARIFICATION_PROMPT = """You are a Compliance Intake Clarification Specialist.
The automated classifier was unable to achieve sufficient certainty (>0.60 confidence) for the AI system described.
Do not guess or assume missing technical or operational facts.

Generate 2 to 4 targeted, specific questions for the user to resolve ambiguity regarding:
1. Exact system purpose and autonomy level (decision support vs. autonomous execution).
2. Underlying data categories (are biometric, health, or social behaviour data used?).
3. Specific target demographic and sector deployment.

Respond strictly with a JSON object:
{
  "clarification_questions": [
    "Question 1...",
    "Question 2..."
  ],
  "reason_for_clarification": "Why confidence was low"
}
"""


async def clarification_agent_node(state: GraphState) -> Dict[str, Any]:
    """Generates precise follow-up questions when confidence falls below the threshold."""
    logger.info("Executing clarification_agent_node for Case %s", state.get("case_id"))

    intake = state.get("structured_intake") or {}
    confidence = state.get("classification_confidence", 0.0)

    messages = [
        {"role": "system", "content": CLARIFICATION_PROMPT},
        {
            "role": "user",
            "content": f"Current Intake State:\n{json.dumps(intake, indent=2)}\nCurrent Confidence Score: {confidence}",
        },
    ]

    response = await llm_router.complete(
        agent_name="CLARIFICATION_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
    )

    questions = []
    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        questions = data.get("clarification_questions", [])
    except Exception as e:
        logger.warning("Clarification JSON parse error (%s). Using fallback inquiries.", e)
        questions = [
            "Does the AI system make fully automated decisions, or does a human credit officer make the final binding determination?",
            "What specific customer data categories are processed (e.g., credit bureau scores, bank transactions, social media)?",
            "In what exact legal jurisdiction and banking subsidiary will this model operate?",
        ]

    logger.info("Clarification agent issued %d questions due to low confidence (%.2f).", len(questions), confidence)

    return {
        "clarification_needed": True,
        "clarification_questions": questions,
        "graph_status": "awaiting_clarification",
        "current_node": "clarification_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
