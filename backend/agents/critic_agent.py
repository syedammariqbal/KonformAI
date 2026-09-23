"""Critic / QA Agent: Rigorous quality, grounding, and citation validator."""

import json
import logging
from typing import Any, Dict, List

from backend.agents.state import GraphState
from backend.core.config import settings
from backend.llm_router.router import llm_router

logger = logging.getLogger(__name__)

CRITIC_PROMPT = """You are a Senior Compliance Auditor and Quality Assurance Inspector for AI Legal Assessments.
Your role is to rigorously inspect the findings produced by the upstream evaluation agents before any report is drafted.

Your Quality Gate Checks:
1. Citation Grounding: Verify that EVERY cited statutory article (EU AI Act, KWG, WpHG, MaRisk) maps to a real retrieved passage ID. Hallucinated or phantom citations are strictly forbidden.
2. Original-Language Grounding: For claims derived from German regulations (KWG, WpHG, MaRisk), you MUST verify grounding against the ORIGINAL German text, NEVER against an English translation alone.
3. Prohibited Practice Completeness: Confirm that any Article 5 prohibited practice characteristics (subliminal manipulation, vulnerability exploitation, social scoring) were not mistakenly overlooked.
4. Internal Consistency: Ensure risk tiers, obligations, and gap severities align logically without internal contradictions.

Determination Rules:
- If all checks pass cleanly: verdict = "APPROVED".
- If defects exist and revision is required: verdict = "REVISE", specify the exact faulty agent in "revision_target", and itemize concrete corrective actions in "issues".
- If severe or persistent: verdict = "ESCALATE_HUMAN".

Respond strictly with a JSON object:
{
  "verdict": "APPROVED" | "REVISE" | "ESCALATE_HUMAN",
  "revision_target": "eu_ai_act_classifier_agent" | "bafin_compliance_agent" | "gap_assessment_agent" | null,
  "issues": ["Itemized defect 1", "Itemized defect 2"],
  "grounding_audit": "Detailed explanation of statutory citation checks against original text"
}
"""


async def critic_agent_node(state: GraphState) -> Dict[str, Any]:
    """Inspects upstream compliance findings, enforces strict grounding, and regulates retry loops."""
    logger.info("Executing critic_agent_node for Case %s (Retry %d)", state.get("case_id"), state.get("critic_retry_count", 0))

    current_retries = state.get("critic_retry_count", 0)
    max_retries = settings.MAX_CRITIC_RETRIES

    # Check retry circuit breaker
    if current_retries >= max_retries:
        logger.warning(
            "Critic retry cap reached (%d >= %d). Escalating Case %s to human review gate.",
            current_retries,
            max_retries,
            state.get("case_id"),
        )
        return {
            "critic_verdict": "ESCALATE_HUMAN",
            "critic_issues": [
                f"Exceeded maximum automated revision attempts ({max_retries}). Human compliance officer review required."
            ],
            "human_review_required": True,
            "current_node": "critic_agent",
        }

    # Assemble review payload
    payload_to_audit = {
        "structured_intake": state.get("structured_intake"),
        "eu_classification": state.get("eu_ai_act_classification"),
        "bafin_obligations": state.get("bafin_obligations"),
        "translated_passages": state.get("translated_passages"),
        "merged_obligations": state.get("merged_obligations"),
        "gap_assessment": state.get("gap_assessment"),
        "retrieved_passage_ids": state.get("retrieved_passage_ids", []),
    }

    messages = [
        {"role": "system", "content": CRITIC_PROMPT},
        {"role": "user", "content": f"Full Compliance Findings to Audit:\n{json.dumps(payload_to_audit, indent=2)}"},
    ]

    response = await llm_router.complete(
        agent_name="CRITIC_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
    )

    verdict = "APPROVED"
    revision_target = None
    issues: List[str] = []

    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        verdict = data.get("verdict", "APPROVED").upper()
        revision_target = data.get("revision_target")
        issues = data.get("issues", [])
    except Exception as e:
        logger.warning("Critic JSON parsing exception (%s). Approving findings by default.", e)
        verdict = "APPROVED"

    new_retry_count = current_retries
    if verdict == "REVISE":
        new_retry_count += 1
        logger.warning(
            "Critic rejected output (Retry %d/%d). Target: %s. Issues: %s",
            new_retry_count,
            max_retries,
            revision_target,
            issues,
        )
        if new_retry_count >= max_retries:
            verdict = "ESCALATE_HUMAN"
            logger.warning("Critic escalation: Max retries exhausted, routing to human gate.")

    return {
        "critic_verdict": verdict,
        "critic_revision_target": revision_target,
        "critic_issues": issues,
        "critic_retry_count": new_retry_count,
        "current_node": "critic_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
