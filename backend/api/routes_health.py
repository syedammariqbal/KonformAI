"""Health and metrics API endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.db.session import get_db
from backend.llm_router.token_tracker import token_tracker

router = APIRouter()


@router.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Health check endpoint confirming database connectivity and operational status."""
    db_healthy = False
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False

    return {
        "status": "healthy" if db_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "database_connected": db_healthy,
        "dry_run_mode": settings.GLOBAL_DRY_RUN,
        "notifications_enabled": settings.ENABLE_NOTIFICATIONS,
    }


@router.get("/metrics", tags=["Observability"])
def get_system_metrics() -> Dict[str, Any]:
    """Returns token consumption and budget metrics."""
    return {
        "daily_token_budget": settings.DAILY_TOKEN_BUDGET,
        "cumulative_daily_tokens": token_tracker._cumulative_daily_tokens,
        "budget_near_exhaustion": token_tracker.is_budget_near_exhaustion(),
        "max_critic_retries": settings.MAX_CRITIC_RETRIES,
        "confidence_threshold": settings.CLASSIFICATION_CONFIDENCE_THRESHOLD,
    }
