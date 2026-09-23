"""SQLAlchemy database models for KonformAI."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Case(Base):
    """Represents a compliance evaluation case for an AI system."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    system_name: Mapped[str] = mapped_column(String(255), default="Unnamed AI System")
    system_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )  # pending, running, awaiting_clarification, awaiting_human_review, approved, rejected, halted_injection, completed, failed
    risk_tier: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default=None
    )  # prohibited, high, limited, minimal, gpai
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None
    )
    is_prohibited_practice: Mapped[bool] = mapped_column(Boolean, default=False)
    structured_intake: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    gap_assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    final_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="case", cascade="all, delete-orphan"
    )
    llm_calls: Mapped[List["LLMCallLog"]] = relationship(
        "LLMCallLog", back_populates="case", cascade="all, delete-orphan"
    )
    human_reviews: Mapped[List["HumanReviewDecision"]] = relationship(
        "HumanReviewDecision", back_populates="case", cascade="all, delete-orphan"
    )


class AuditLog(Base):
    """Durable audit trail capturing state transitions, human decisions, and security halts."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    actor: Mapped[str] = mapped_column(String(100), default="system")
    node_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    case: Mapped[Optional["Case"]] = relationship("Case", back_populates="audit_logs")


class LLMCallLog(Base):
    """Observability table logging every LLM invocation, tokens, cost, latency, and failovers."""

    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    failover_occurred: Mapped[bool] = mapped_column(Boolean, default=False)
    failover_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_window_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    case: Mapped[Optional["Case"]] = relationship("Case", back_populates="llm_calls")


class HumanReviewDecision(Base):
    """Records human-in-the-loop decisions (approve / edit / reject)."""

    __tablename__ = "human_review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(50))  # approve, edit, reject
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), default="compliance_officer")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    case: Mapped["Case"] = relationship("Case", back_populates="human_reviews")


class KnowledgeBaseDocument(Base):
    """Metadata tracking for ingested regulatory corpus and uploaded user policy documents."""

    __tablename__ = "knowledge_base_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String(255))
    source_category: Mapped[str] = mapped_column(
        String(50), index=True
    )  # eu_ai_act, bafin, wphg_kwg, uploaded
    language: Mapped[str] = mapped_column(String(10), default="en")  # en, de
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    pii_scan_status: Mapped[str] = mapped_column(
        String(50), default="clean"
    )  # clean, redacted, flagged
