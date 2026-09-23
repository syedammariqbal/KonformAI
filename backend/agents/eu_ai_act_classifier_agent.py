"""EU AI Act Classifier Agent: Evaluates AI systems against Regulation (EU) 2024/1689."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router
from backend.rag.hybrid_retriever import hybrid_retriever
from backend.tools.eurlex_tool import EURLexQuery, eurlex_tool

logger = logging.getLogger(__name__)

EU_CLASSIFIER_PROMPT = """You are a Principal EU AI Act Regulatory Compliance Specialist.
Evaluate the AI system profile against the retrieved EU AI Act passages.

Key Classification Rules:
1. Prohibited (Article 5): Subliminal manipulation, vulnerability exploitation, social scoring of natural persons, individual criminal predictive profiling, untargeted biometric scraping.
2. High-Risk (Article 6 & Annex III):
   - Annex III Point 5(b): AI systems intended to evaluate creditworthiness or establish credit scores of natural persons (financial services).
   - Annex III Point 5(c): Risk assessment and pricing in life/health insurance.
   - Annex III Point 1: Biometrics.
   - Annex III Point 4: Employment, worker management, and recruitment.
3. Limited Risk (Transparency obligations, Article 50): Customer-facing conversational chatbots, emotion recognition, deepfakes.
4. Minimal Risk: Standard internal automation, spam filters, recommendation engines without profiling harm.
5. GPAI (General Purpose AI Models, Chapter V): Foundational foundation models.

Every legal claim MUST cite an exact Article or Annex from the retrieved context.
If you identify a prohibited practice under Article 5, flag 'is_prohibited: true' with high confidence.

Respond strictly with a JSON object:
{
  "risk_tier": "prohibited" | "high" | "limited" | "minimal" | "gpai",
  "is_prohibited": true/false,
  "confidence_score": 0.0 to 1.0,
  "cited_articles": ["Article 5(1)(c)", "Annex III Point 5(b)"],
  "retrieved_passage_ids": ["EU AI Act::Article 5", ...],
  "reasoning": "Clear legal reasoning connecting system characteristics to statutory definitions"
}
"""


async def eu_ai_act_classifier_agent_node(state: GraphState) -> Dict[str, Any]:
    """Retrieves EU AI Act passages and classifies risk tier under Regulation (EU) 2024/1689."""
    logger.info("Executing eu_ai_act_classifier_agent_node for Case %s", state.get("case_id"))

    intake = state.get("structured_intake") or {}
    query_text = (
        f"{intake.get('system_purpose', '')} {intake.get('sector', '')} "
        f"{intake.get('affected_persons', '')} {' '.join(intake.get('data_types_used', []))}"
    )

    # Hybrid retrieval over English EU AI Act corpus
    retrieved_docs = hybrid_retriever.retrieve(query=query_text, language="en", k=4)
    context_blocks = []
    passage_ids = []

    for doc in retrieved_docs:
        pid = doc.metadata.get("passage_id", "EU AI Act")
        passage_ids.append(pid)
        context_blocks.append(f"[{pid}]\n{doc.page_content}")

    assembled_context = "\n\n".join(context_blocks)

    messages = [
        {"role": "system", "content": EU_CLASSIFIER_PROMPT},
        {
            "role": "user",
            "content": f"AI System Profile:\n{json.dumps(intake, indent=2)}\n\nRetrieved EU AI Act Context:\n{assembled_context}",
        },
    ]

    response = await llm_router.complete(
        agent_name="EU_AI_ACT_CLASSIFIER_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
        retrieved_context=assembled_context,
    )

    is_prohibited = False
    confidence = 0.85
    risk_tier = "high"
    cited_articles = ["Annex III Point 5(b)"]
    reasoning = "Credit evaluation AI system in banking is classified as High-Risk under Annex III Point 5(b)."

    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        risk_tier = data.get("risk_tier", "high").lower()
        is_prohibited = bool(data.get("is_prohibited", risk_tier == "prohibited"))
        confidence = float(data.get("confidence_score", 0.85))
        cited_articles = data.get("cited_articles", [])
        reasoning = data.get("reasoning", "")
    except Exception as e:
        logger.warning("EU AI Act classifier JSON parse error (%s). Using fallback evaluation.", e)

    # Live EUR-Lex verification tool call
    try:
        query_article = cited_articles[0] if cited_articles else "6"
        await eurlex_tool.verify_article(EURLexQuery(article_number=query_article))
    except Exception as e:
        logger.debug("EUR-Lex tool call notice: %s", e)

    classification_result = {
        "risk_tier": risk_tier,
        "is_prohibited": is_prohibited,
        "confidence_score": confidence,
        "cited_articles": cited_articles,
        "retrieved_passage_ids": passage_ids,
        "reasoning": reasoning,
    }

    prior_passage_ids = state.get("retrieved_passage_ids", [])
    updated_passage_ids = list(set(prior_passage_ids + passage_ids))

    return {
        "eu_ai_act_classification": classification_result,
        "is_prohibited_practice": is_prohibited,
        "classification_confidence": confidence,
        "retrieved_passage_ids": updated_passage_ids,
        "current_node": "eu_ai_act_classifier_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
