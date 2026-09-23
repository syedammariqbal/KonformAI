"""Translation Agent: Renders German statutory passages into English with binding disclaimers.

Preserves original German text alongside translations to ensure the Critic agent
validates grounding strictly against authentic statutory text.
"""

import json
import logging
from typing import Any, Dict, List

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router

logger = logging.getLogger(__name__)

STANDARD_TRANSLATION_DISCLAIMER = (
    "This English rendering is provided for convenience and information purposes only. "
    "It is not a certified legal translation. The original German text remains the sole authoritative "
    "and legally binding text in all respects."
)

MARISK_SPECIFIC_DISCLAIMER = (
    "This English version is provided for information purposes only. "
    "The original German text is binding in all respects (BaFin Circular 10/2021 MaRisk)."
)

TRANSLATION_PROMPT = """You are a Legal Translator specializing in German financial supervisory terminology (BaFin, KWG, WpHG, MaRisk).
Your task is to accurately translate retrieved German regulatory passages into clear, precise legal English.

CRITICAL INSTRUCTIONS:
1. Translate each German passage into accurate legal English.
2. You MUST keep the exact original German text attached to each translation.
3. You MUST keep the exact statutory citation (statute, section, paragraph, passage ID).
4. Never omit the original German text.

Respond strictly with a JSON object:
{
  "translations": [
    {
      "source_citation": "e.g. MaRisk AT 4.3.2 Tz. 1",
      "passage_id": "Exact passage ID",
      "original_de": "Exact original German statutory text",
      "english_translation": "Faithful, professional legal English translation",
      "disclaimer": "Standard non-binding translation disclaimer"
    }
  ]
}
"""


async def translation_agent_node(state: GraphState) -> Dict[str, Any]:
    """Translates German regulatory passages while anchoring original text and disclaimers."""
    logger.info("Executing translation_agent_node for Case %s", state.get("case_id"))

    bafin_data = state.get("bafin_obligations") or {}
    obligations = bafin_data.get("applicable_obligations", [])

    # Filter for German obligations
    de_passages = [ob for ob in obligations if ob.get("language") == "de" or ob.get("original_text")]

    if not de_passages:
        # Check if generic German snippets in bafin summary
        de_passages = obligations

    messages = [
        {"role": "system", "content": TRANSLATION_PROMPT},
        {
            "role": "user",
            "content": f"German Regulatory Obligations to Translate:\n{json.dumps(de_passages, indent=2)}",
        },
    ]

    response = await llm_router.complete(
        agent_name="TRANSLATION_AGENT",
        messages=messages,
        case_id=state.get("case_id"),
    )

    translated_list: List[Dict[str, Any]] = []
    try:
        cleaned = response.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        translated_list = data.get("translations", [])
    except Exception as e:
        logger.warning("Translation JSON parse error (%s). Using fallback translation block.", e)
        for ob in de_passages:
            is_marisk = "marisk" in str(ob.get("source", "")).lower()
            disclaimer = MARISK_SPECIFIC_DISCLAIMER if is_marisk else STANDARD_TRANSLATION_DISCLAIMER
            translated_list.append({
                "source_citation": ob.get("source", "German Statute"),
                "passage_id": ob.get("passage_id", "Statutory Source"),
                "original_de": ob.get("original_text") or ob.get("obligation", ""),
                "english_translation": ob.get("obligation", ""),
                "disclaimer": disclaimer,
            })

    # Ensure disclaimer is populated on all translated entries
    for item in translated_list:
        if not item.get("disclaimer"):
            is_marisk = "marisk" in str(item.get("source_citation", "")).lower()
            item["disclaimer"] = MARISK_SPECIFIC_DISCLAIMER if is_marisk else STANDARD_TRANSLATION_DISCLAIMER

    logger.info("Translation node processed %d statutory passages with binding disclaimers.", len(translated_list))

    return {
        "translated_passages": translated_list,
        "current_node": "translation_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response.input_tokens + response.output_tokens,
    }
