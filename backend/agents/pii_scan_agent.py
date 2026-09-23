"""PII Scan Agent: Inspects uploaded documents and descriptions using Microsoft Presidio."""

import logging
from typing import Any, Dict, List

from backend.agents.state import GraphState
from backend.llm_router.router import llm_router
from backend.tools.presidio_tool import PIIScanRequest, presidio_tool

logger = logging.getLogger(__name__)

PII_SUMMARY_PROMPT = """You are a Data Privacy Officer reviewing a PII scan summary for internal compliance files.
Given the detected PII entities, provide a 1-sentence risk summary for the compliance audit log.
State whether the document is safe for internal reasoning or required redaction.
"""


async def pii_scan_agent_node(state: GraphState) -> Dict[str, Any]:
    """Runs Presidio PII scan on system description and any uploaded document files."""
    logger.info("Executing pii_scan_agent_node for Case %s", state.get("case_id"))

    doc_paths = state.get("uploaded_doc_paths", [])
    scan_results: List[Dict[str, Any]] = []

    # 1. Scan primary system description
    desc = state.get("system_description", "")
    req = PIIScanRequest(text=desc, action="detect")
    result = presidio_tool.scan(req)
    if result.entity_count > 0:
        scan_results.append({
            "source": "system_description",
            "entity_count": result.entity_count,
            "entities": [e.model_dump() for e in result.entities_found],
            "has_high_risk": result.has_high_risk_pii,
        })

    # 2. Scan uploaded documents if any
    for path_str in doc_paths:
        try:
            with open(path_str, "r", encoding="utf-8") as f:
                content = f.read()
            doc_req = PIIScanRequest(text=content, action="redact")
            doc_res = presidio_tool.scan(doc_req)
            scan_results.append({
                "source": path_str,
                "entity_count": doc_res.entity_count,
                "entities": [e.model_dump() for e in doc_res.entities_found],
                "has_high_risk": doc_res.has_high_risk_pii,
                "redacted_text": doc_res.redacted_text,
            })
        except Exception as e:
            logger.error("Error reading file %s during PII scan: %s", path_str, e)

    # 3. LLM summary of privacy findings
    total_pii = sum(r["entity_count"] for r in scan_results)
    summary_text = "No sensitive PII detected."
    response_tokens = 0

    if total_pii > 0:
        messages = [
            {"role": "system", "content": PII_SUMMARY_PROMPT},
            {
                "role": "user",
                "content": f"PII Scan Findings: Total items = {total_pii}. Details: {scan_results}",
            },
        ]
        resp = await llm_router.complete(
            agent_name="PII_SCAN_AGENT",
            messages=messages,
            case_id=state.get("case_id"),
        )
        summary_text = resp.content.strip()
        response_tokens = resp.input_tokens + resp.output_tokens

    logger.info("PII scan completed. Detected entities: %d. Summary: %s", total_pii, summary_text)

    return {
        "pii_scan_results": scan_results,
        "current_node": "pii_scan_agent",
        "token_usage_total": state.get("token_usage_total", 0) + response_tokens,
    }
