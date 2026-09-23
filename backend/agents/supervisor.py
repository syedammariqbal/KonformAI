"""Supervisor Agent Graph: Coordinates multi-agent compliance workflow with conditional edges."""

import logging
from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from backend.agents.bafin_compliance_agent import bafin_compliance_agent_node
from backend.agents.clarification_agent import clarification_agent_node
from backend.agents.conflict_resolution_agent import conflict_resolution_agent_node
from backend.agents.critic_agent import critic_agent_node
from backend.agents.eu_ai_act_classifier_agent import eu_ai_act_classifier_agent_node
from backend.agents.gap_assessment_agent import gap_assessment_agent_node
from backend.agents.injection_sanitizer_agent import injection_sanitizer_agent_node
from backend.agents.intake_agent import intake_agent_node
from backend.agents.pii_scan_agent import pii_scan_agent_node
from backend.agents.report_agent import report_agent_node
from backend.agents.state import GraphState
from backend.agents.translation_agent import translation_agent_node
from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.observability.audit_logger import log_audit_event

logger = logging.getLogger(__name__)


# ============================================================
# Auxiliary Support Nodes
# ============================================================

async def injection_halt_node(state: GraphState) -> Dict[str, Any]:
    """Terminal node executed when prompt injection is identified."""
    logger.critical("Graph halted at injection_halt_node for Case %s", state.get("case_id"))
    return {
        "graph_status": "halted_injection",
        "current_node": "injection_halt_node",
        "error_message": f"Prompt injection halt: {state.get('injection_details')}",
    }


async def parallel_join_node(state: GraphState) -> Dict[str, Any]:
    """Synchronizes parallel classification branches (EU AI Act and BaFin)."""
    logger.info("Synchronized parallel branches for Case %s", state.get("case_id"))
    return {
        "current_node": "parallel_join_node",
    }


async def human_review_gate_node(state: GraphState) -> Dict[str, Any]:
    """Human-in-the-loop gate node. Pauses or acknowledges human sign-off."""
    case_id = state.get("case_id")
    decision = state.get("human_review_decision")
    notes = state.get("human_review_notes")

    logger.info(
        "human_review_gate_node reached for Case %s. Current Decision: %s",
        case_id,
        decision,
    )

    if not decision:
        # Awaiting human input
        return {
            "human_review_required": True,
            "graph_status": "awaiting_human_review",
            "current_node": "human_review_gate",
        }

    return {
        "human_review_required": False,
        "graph_status": f"human_{decision}",
        "current_node": "human_review_gate",
    }


async def export_audit_agent_node(state: GraphState) -> Dict[str, Any]:
    """Deterministic export node persisting full graph run and emitting LangSmith trace link."""
    case_id = state.get("case_id", "unknown")
    logger.info("Executing export_audit_agent_node for Case %s", case_id)

    # Durable Postgres persistence
    with SessionLocal() as db:
        log_audit_event(
            db=db,
            case_id=case_id,
            event_type="GRAPH_COMPLETED",
            actor="export_audit_agent",
            node_name="export_audit_agent",
            details={
                "risk_tier": (state.get("eu_ai_act_classification") or {}).get("risk_tier"),
                "is_prohibited": state.get("is_prohibited_practice", False),
                "critic_retries": state.get("critic_retry_count", 0),
                "human_decision": state.get("human_review_decision", "approved"),
                "total_tokens": state.get("token_usage_total", 0),
                "retrieved_passages_count": len(state.get("retrieved_passage_ids", [])),
            },
        )

    trace_url = f"https://smith.langchain.com/o/default/projects/p/{settings.LANGCHAIN_PROJECT}"

    return {
        "graph_status": "completed",
        "langsmith_trace_url": trace_url,
        "current_node": "export_audit_agent",
    }


# ============================================================
# Conditional Routing Functions
# ============================================================

def route_after_sanitizer(state: GraphState) -> Literal["injection_halt", "pii_scan"]:
    """Routes to immediate halt if injection detected; else continues to PII scan."""
    if state.get("injection_detected"):
        return "injection_halt"
    return "pii_scan"


def route_after_classification(
    state: GraphState,
) -> Literal["clarification", "human_gate_prohibited", "translation", "conflict_resolution"]:
    """Conditional routing based on confidence, Article 5 hard override, and language."""
    # 1. Clarification check: confidence below threshold
    conf = state.get("classification_confidence", 1.0)
    if conf < settings.CLASSIFICATION_CONFIDENCE_THRESHOLD:
        logger.info("Routing to clarification_agent (confidence %.2f < %.2f)", conf, settings.CLASSIFICATION_CONFIDENCE_THRESHOLD)
        return "clarification"

    # 2. Hard override rule: Article 5 prohibited practice skips gap analysis
    if state.get("is_prohibited_practice"):
        logger.critical("Article 5 hard override: Prohibited practice detected! Routing directly to human review gate.")
        return "human_gate_prohibited"

    # 3. Translation check: German source passages present
    if state.get("has_german_passages"):
        logger.info("Routing to translation_agent for German source material.")
        return "translation"

    # 4. Standard path
    return "conflict_resolution"


def route_after_critic(
    state: GraphState,
) -> Literal["report", "revise_eu", "revise_bafin", "revise_gap", "escalate_human"]:
    """Routes approved output to report drafting, or enforces retry loop / human escalation."""
    verdict = state.get("critic_verdict", "APPROVED")
    target = state.get("critic_revision_target")
    retry_count = state.get("critic_retry_count", 0)

    if verdict == "APPROVED":
        return "report"

    if verdict == "ESCALATE_HUMAN" or retry_count >= settings.MAX_CRITIC_RETRIES:
        return "escalate_human"

    # Route back to specific faulty agent
    if target == "eu_ai_act_classifier_agent":
        return "revise_eu"
    if target == "bafin_compliance_agent":
        return "revise_bafin"
    return "revise_gap"


def route_after_human_gate(state: GraphState) -> Literal["export_audit", "re_report", "end"]:
    """Routes human decision: approve -> export, edit -> re-draft report, reject -> end."""
    decision = (state.get("human_review_decision") or "approved").lower()
    if decision == "approve" or decision == "approved":
        return "export_audit"
    if decision == "edit":
        return "re_report"
    return "end"


# ============================================================
# StateGraph Assembly
# ============================================================

def create_compliance_graph() -> StateGraph:
    """Builds and compiles the KonformAI multi-agent StateGraph."""
    workflow = StateGraph(GraphState)

    # Register all nodes
    workflow.add_node("intake_agent", intake_agent_node)
    workflow.add_node("injection_sanitizer_agent", injection_sanitizer_agent_node)
    workflow.add_node("injection_halt", injection_halt_node)
    workflow.add_node("pii_scan_agent", pii_scan_agent_node)
    workflow.add_node("eu_ai_act_classifier_agent", eu_ai_act_classifier_agent_node)
    workflow.add_node("bafin_compliance_agent", bafin_compliance_agent_node)
    workflow.add_node("parallel_join", parallel_join_node)
    workflow.add_node("clarification_agent", clarification_agent_node)
    workflow.add_node("translation_agent", translation_agent_node)
    workflow.add_node("conflict_resolution_agent", conflict_resolution_agent_node)
    workflow.add_node("gap_assessment_agent", gap_assessment_agent_node)
    workflow.add_node("critic_agent", critic_agent_node)
    workflow.add_node("report_agent", report_agent_node)
    workflow.add_node("human_review_gate", human_review_gate_node)
    workflow.add_node("export_audit_agent", export_audit_agent_node)

    # 1. Entry point & Injection Sanitization
    workflow.add_edge(START, "intake_agent")
    workflow.add_edge("intake_agent", "injection_sanitizer_agent")

    workflow.add_conditional_edges(
        "injection_sanitizer_agent",
        route_after_sanitizer,
        {
            "injection_halt": "injection_halt",
            "pii_scan": "pii_scan_agent",
        },
    )
    workflow.add_edge("injection_halt", END)

    # 2. Parallel fan-out: EU AI Act Classifier & BaFin Compliance Agent
    workflow.add_edge("pii_scan_agent", "eu_ai_act_classifier_agent")
    workflow.add_edge("eu_ai_act_classifier_agent", "bafin_compliance_agent")
    workflow.add_edge("bafin_compliance_agent", "parallel_join")

    # 3. Post-Classification Conditional Routing
    workflow.add_conditional_edges(
        "parallel_join",
        route_after_classification,
        {
            "clarification": "clarification_agent",
            "human_gate_prohibited": "human_review_gate",  # Article 5 Hard Override
            "translation": "translation_agent",
            "conflict_resolution": "conflict_resolution_agent",
        },
    )

    # Clarification loops back to intake
    workflow.add_edge("clarification_agent", "intake_agent")

    # Translation routes to conflict resolution
    workflow.add_edge("translation_agent", "conflict_resolution_agent")

    # 4. Harmonization & Gap Assessment
    workflow.add_edge("conflict_resolution_agent", "gap_assessment_agent")
    workflow.add_edge("gap_assessment_agent", "critic_agent")

    # 5. Critic QA & Retry Routing
    workflow.add_conditional_edges(
        "critic_agent",
        route_after_critic,
        {
            "report": "report_agent",
            "revise_eu": "eu_ai_act_classifier_agent",
            "revise_bafin": "bafin_compliance_agent",
            "revise_gap": "gap_assessment_agent",
            "escalate_human": "human_review_gate",
        },
    )

    # 6. Report drafting & Human Review Gate
    workflow.add_edge("report_agent", "human_review_gate")

    workflow.add_conditional_edges(
        "human_review_gate",
        route_after_human_gate,
        {
            "export_audit": "export_audit_agent",
            "re_report": "report_agent",
            "end": END,
        },
    )

    workflow.add_edge("export_audit_agent", END)

    return workflow


# Compiled singleton graph
compliance_graph = create_compliance_graph().compile()
