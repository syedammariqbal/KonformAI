"""Audit logger module for writing durable compliance events to PostgreSQL."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AuditLog

logger = logging.getLogger(__name__)


def log_audit_event(
    db: Session,
    case_id: Optional[str],
    event_type: str,
    actor: str = "system",
    details: Optional[Dict[str, Any]] = None,
    node_name: Optional[str] = None,
) -> AuditLog:
    """Persists a compliance event to the audit_log table."""
    event = AuditLog(
        case_id=case_id,
        event_type=event_type,
        actor=actor,
        node_name=node_name,
        details=details or {},
        timestamp=datetime.now(timezone.utc),
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        logger.info(
            "Audit event logged: [%s] by '%s' on node '%s' for Case %s",
            event_type,
            actor,
            node_name,
            case_id,
        )
        return event
    except Exception as exc:
        logger.error("Failed to write audit event: %s", exc)
        db.rollback()
        return event


def get_audit_trail(db: Session, case_id: str) -> List[AuditLog]:
    """Retrieves all chronological audit events for a given case."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.timestamp.asc())
    )
    return list(db.scalars(stmt).all())


def get_recent_audit_logs(db: Session, limit: int = 50) -> List[AuditLog]:
    """Retrieves recent audit events across all cases."""
    stmt = (
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
