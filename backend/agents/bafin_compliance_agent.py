"""BaFin Compliance Agent: Cross-references German banking regulations (KWG, WpHG, MaRisk, BaFin BDAI)."""

import json
import logging
from typing import Any, Dict

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router
from backend.rag.hybrid_retriever import hybrid_retriever

logger = logging.getLogger(__name__)

BAFIN_PROMPT = """You are a Senior Regulatory Counsel specializing in German financial supervisory law (BaFin, KWG, WpHG, MaRisk).
Evaluate the AI system profile against retrieved German regulatory passages.

Key German Regulatory Rules:
1. MaRisk AT 4.3.2: Mandates rigorous Model Risk Management (Modellrisikomanagement) for all quantitative models used in credit decisioning, risk measurement, and pricing. Independent validation and backtesting are legally mandatory.
2. KWG § 25a: Requires proper business organization, adequate internal risk controls, and IT security infrastructure.
3. WpHG § 63, § 80: Governs automated investment advice (Robo-Advice) and algorithmic systems, requiring client profiling, appropriateness checks, and emergency stop-switches.
4. BaFin BDAI Principles (2021): Algorithmic explainability, board responsibility, and avoidance of unintended bias.
5. BaFin 2026 AI/ICT Risk Guidance (DORA alignment): AI treated as critical ICT service; prompt-injection defenses and manual fallback procedures required.

Identify all applicable German supervisory requirements.
Cite the exact German statutes, circulars, or principles. Note whether passages are original German (language=de).

Respond strictly with a JSON object:
{
  "applicable_obligations": [
    {
      "source": "MaRisk AT 4.3.2 (Tz. 1)",
      "obligation": "Mandatory model risk governance, independent validation prior to deployment, and backtesting.",
      "passage_id": "BaFin MaRisk (Rundschreiben 10/2021)::AT 4.3.2",
      "language": "de",
      "original_text": "Original German citation snippet if applicable"
    }
  ],
  "confidence_score": 0.0 to 1.0,
  "has_german_sources": true/false,
  "summary": "Concise synthesis of German compliance mandates"
}
"""


async def bafin_compliance_agent_node(state: GraphState) -> Dict[str, Any]:
    """Retrieves BaFin/KWG/WpHG passages and identifies German-specific regulatory obligations."""
    logger.info("Executing bafin_compliance_agent_node for Case %s", state.get("case_id"))

    intake = state.get("structured_intake") or {}
    query_text = (
        f"{intake.get('system_purpose', '')} {intake.get('sector', '')} "
        f"Kreditentscheidung Risikomanagement Modellvalidierung {intake.get('deployment_context', '')}"
    )

    # Hybrid retrieval over BaFin corpus (querying both German and English indexes)
    retrieved_docs_de = hybrid_retriever.retrieve(query=query_text, language="de", k=3)
    retrieved_docs_en = hybrid_retriever.retrieve(query=query_text, language="en", k=2)

    retrieved_docs = retrieved_docs_de + retrieved_docs_en
    context_blocks = []
    passage_ids = []
    has_german_passages = False

    for doc in retrieved_docs:
        pid = doc.metadata.get("passage_id", "BaFin Corpus")
        lang = doc.metadata.get("language", "en")
        if lang == "de":
            has_german_passages = True
        passage_ids.append(pid)
        context_blocks.append(f"[{pid} | Lang: {lang}]\n{doc.page_content}")

    assembled_context = "\n\n".join(context_blocks)

    messages = [
        {"role": "system", "content": BAFIN_PROMPT},
        {
            "role": "user",
            "content": f"AI System Profile:\n{json.dumps(intake, indent=2)}\n\nRetrieved BaFin & Federal Statutes Context:\n{assembled_context}",
        },
    ]

    response = await llm_router.complete(
        agent_name="BAFIN_COMPLIANCE_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
        retrieved_context=assembled_context,
    )

    obligations = []
    confidence = 0.88
    summary = "System subject to MaRisk AT 4.3.2 model risk governance and KWG § 25a organisational controls."

    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        obligations = data.get("applicable_obligations", [])
        confidence = float(data.get("confidence_score", 0.88))
        summary = data.get("summary", "")
        if data.get("has_german_sources"):
            has_german_passages = True
    except Exception as e:
        logger.warning("BaFin agent JSON parse error (%s). Using fallback obligations.", e)

    prior_passage_ids = state.get("retrieved_passage_ids", [])
    updated_passage_ids = list(set(prior_passage_ids + passage_ids))

    bafin_result = {
        "applicable_obligations": obligations,
        "confidence_score": confidence,
        "summary": summary,
        "retrieved_passage_ids": passage_ids,
        "has_german_passages": has_german_passages,
    }

    return {
        "bafin_obligations": bafin_result,
        "has_german_passages": has_german_passages,
        "retrieved_passage_ids": updated_passage_ids,
        "current_node": "bafin_compliance_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
