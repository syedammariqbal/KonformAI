"""FastAPI routes for initiating compliance classifications and querying case status."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.agents.supervisor import compliance_graph
from backend.core.security import verify_api_token
from backend.db.models import Case
from backend.db.session import SessionLocal, get_db
from backend.observability.audit_logger import get_audit_trail, log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter()


class ClassificationRequest(BaseModel):
    """Input payload to start a new compliance evaluation."""

    system_name: str = Field(default="AI System", description="Identifier or name of the AI system")
    system_description: str = Field(..., description="Comprehensive description of AI system architecture, data, and deployment context")
    uploaded_doc_paths: List[str] = Field(default_factory=list, description="Local paths to uploaded policy or control documents")


class ClassificationResponse(BaseModel):
    """Response returned immediately upon case submission."""

    case_id: str
    status: str
    system_name: str


async def _execute_graph_background(case_id: str, system_description: str, doc_paths: List[str]) -> None:
    """Runs the compiled LangGraph compliance workflow in the background and updates database."""
    logger.info("Background execution started for Case %s", case_id)

    initial_state = {
        "case_id": case_id,
        "system_description": system_description,
        "uploaded_doc_paths": doc_paths,
        "structured_intake": None,
        "injection_detected": False,
        "injection_details": None,
        "pii_scan_results": [],
        "eu_ai_act_classification": None,
        "bafin_obligations": None,
        "has_german_passages": False,
        "translated_passages": [],
        "merged_obligations": None,
        "classification_confidence": 1.0,
        "clarification_needed": False,
        "clarification_questions": [],
        "clarification_responses": [],
        "is_prohibited_practice": False,
        "gap_assessment": None,
        "critic_verdict": None,
        "critic_revision_target": None,
        "critic_issues": [],
        "critic_retry_count": 0,
        "final_report": None,
        "human_review_required": False,
        "human_review_decision": None,
        "human_review_notes": None,
        "retrieved_passage_ids": [],
        "token_usage_total": 0,
        "cost_total": 0.0,
        "langsmith_trace_url": None,
        "current_node": "start",
        "graph_status": "running",
        "error_message": None,
    }

    try:
        final_state = await compliance_graph.ainvoke(initial_state)

        with SessionLocal() as db:
            case = db.get(Case, case_id)
            if case:
                case.status = final_state.get("graph_status", "completed")
                eu_eval = final_state.get("eu_ai_act_classification") or {}
                case.risk_tier = eu_eval.get("risk_tier")
                case.confidence_score = final_state.get("classification_confidence")
                case.is_prohibited_practice = final_state.get("is_prohibited_practice", False)
                case.structured_intake = final_state.get("structured_intake")
                case.gap_assessment = final_state.get("gap_assessment")
                case.final_report = final_state.get("final_report")
                db.commit()

                log_audit_event(
                    db=db,
                    case_id=case_id,
                    event_type="CASE_STATE_UPDATED",
                    actor="background_executor",
                    node_name=final_state.get("current_node"),
                    details={"status": case.status, "risk_tier": case.risk_tier},
                )
        logger.info("Case %s background execution finished with status '%s'.", case_id, final_state.get("graph_status"))

    except Exception as exc:
        logger.exception("Error during graph execution for Case %s: %s", case_id, exc)
        with SessionLocal() as db:
            case = db.get(Case, case_id)
            if case:
                case.status = "failed"
                db.commit()
                log_audit_event(
                    db=db,
                    case_id=case_id,
                    event_type="CASE_EXECUTION_FAILED",
                    actor="background_executor",
                    details={"error": str(exc)},
                )


@router.post("/classify", response_model=ClassificationResponse, status_code=status.HTTP_202_ACCEPTED, tags=["Classification"])
def submit_classification(
    request: ClassificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> ClassificationResponse:
    """Submits a new AI system description and triggers the LangGraph agent run asynchronously."""
    new_case = Case(
        system_name=request.system_name,
        system_description=request.system_description,
        status="running",
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    log_audit_event(
        db=db,
        case_id=new_case.id,
        event_type="CASE_CREATED",
        actor="compliance_user",
        details={"system_name": request.system_name},
    )

    # Launch graph in background
    background_tasks.add_task(
        _execute_graph_background,
        new_case.id,
        request.system_description,
        request.uploaded_doc_paths,
    )

    return ClassificationResponse(
        case_id=new_case.id,
        status=new_case.status,
        system_name=new_case.system_name,
    )


@router.get("/cases", response_model=List[Dict[str, Any]], tags=["Classification"])
def list_cases(
    limit: int = 20,
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> List[Dict[str, Any]]:
    """Lists recent compliance evaluation cases."""
    stmt = select(Case).order_by(desc(Case.created_at)).limit(limit)
    cases = db.scalars(stmt).all()
    return [
        {
            "id": c.id,
            "system_name": c.system_name,
            "status": c.status,
            "risk_tier": c.risk_tier,
            "confidence_score": c.confidence_score,
            "is_prohibited": c.is_prohibited_practice,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]


@router.get("/cases/{case_id}", tags=["Classification"])
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> Dict[str, Any]:
    """Returns detailed state, findings, and audit trail for a specific case."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    audit_trail = get_audit_trail(db, case_id)

    return {
        "id": case.id,
        "system_name": case.system_name,
        "system_description": case.system_description,
        "status": case.status,
        "risk_tier": case.risk_tier,
        "confidence_score": case.confidence_score,
        "is_prohibited_practice": case.is_prohibited_practice,
        "structured_intake": case.structured_intake,
        "gap_assessment": case.gap_assessment,
        "has_final_report": case.final_report is not None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "audit_trail": [
            {
                "event_type": a.event_type,
                "actor": a.actor,
                "node_name": a.node_name,
                "details": a.details,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in audit_trail
        ],
    }


@router.get("/cases/{case_id}/report", tags=["Classification"])
def get_case_report(
    case_id: str,
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> Dict[str, Any]:
    """Returns the compiled final compliance report."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.final_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report is not yet generated or case is currently running.",
        )

    return {
        "case_id": case.id,
        "system_name": case.system_name,
        "status": case.status,
        "final_report": case.final_report,
    }
