"""FastAPI routes for human-in-the-loop review actions (approve / edit / reject)."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.security import verify_api_token
from backend.db.models import Case, HumanReviewDecision
from backend.db.session import get_db
from backend.observability.audit_logger import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter()


class HumanReviewRequest(BaseModel):
    """Payload submitted by a compliance officer or reviewer."""

    decision: Literal["approve", "edit", "reject"] = Field(
        ..., description="Review action decision"
    )
    reviewer_notes: Optional[str] = Field(
        default=None, description="Optional justification or requested revisions"
    )
    actor: str = Field(default="compliance_officer", description="Identity or role of human reviewer")


class HumanReviewResponse(BaseModel):
    """Result of human review recording."""

    case_id: str
    decision: str
    updated_status: str
    message: str


@router.post("/cases/{case_id}/review", response_model=HumanReviewResponse, tags=["Human Review"])
def review_case(
    case_id: str,
    request: HumanReviewRequest,
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> HumanReviewResponse:
    """Records human review decision (approve, edit, reject) and updates audit log."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    decision_record = HumanReviewDecision(
        case_id=case_id,
        decision=request.decision,
        reviewer_notes=request.reviewer_notes,
        actor=request.actor,
    )
    db.add(decision_record)

    new_status = f"human_{request.decision}"
    if request.decision == "approve":
        new_status = "approved"
    elif request.decision == "reject":
        new_status = "rejected"
    elif request.decision == "edit":
        new_status = "awaiting_revision"

    case.status = new_status
    db.commit()

    log_audit_event(
        db=db,
        case_id=case_id,
        event_type="HUMAN_REVIEW_DECISION",
        actor=request.actor,
        node_name="human_review_gate",
        details={
            "decision": request.decision,
            "reviewer_notes": request.reviewer_notes,
            "new_status": new_status,
        },
    )

    logger.info("Human review decision '%s' recorded for Case %s by '%s'", request.decision, case_id, request.actor)

    return HumanReviewResponse(
        case_id=case_id,
        decision=request.decision,
        updated_status=new_status,
        message=f"Case status successfully transitioned to {new_status}.",
    )
