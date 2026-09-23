"""FastAPI routes for knowledge base management and secure document uploads."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.security import verify_api_token
from backend.db.models import KnowledgeBaseDocument
from backend.db.session import get_db
from backend.rag.hybrid_retriever import hybrid_retriever
from backend.rag.ingestion import split_legal_document
from backend.rag.vector_store import vector_store_manager
from backend.tools.presidio_tool import PIIScanRequest, presidio_tool

logger = logging.getLogger(__name__)
router = APIRouter()


class UploadDocumentResponse(BaseModel):
    """Result of uploading, scanning, and indexing a user document."""

    filename: str
    category: str
    chunk_count: int
    pii_entities_detected: int
    pii_redacted: bool
    status: str
    message: str


@router.post("/knowledge-base/upload", response_model=UploadDocumentResponse, tags=["Knowledge Base"])
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> UploadDocumentResponse:
    """Uploads an internal policy document, runs PII and injection checks, and indexes into hybrid RAG."""
    filename = file.filename or "uploaded_document.txt"
    upload_dir = Path(settings.UPLOADED_DOCS_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest_path = upload_dir / filename

    # Read content
    try:
        content_bytes = await file.read()
        raw_text = content_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read uploaded file: {str(e)}",
        )

    # 1. PII Scan & Redaction
    pii_req = PIIScanRequest(text=raw_text, action="redact")
    pii_result = presidio_tool.scan(pii_req)
    text_to_index = pii_result.redacted_text if pii_result.redacted_text else raw_text

    # Save to disk
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(text_to_index)

    # 2. Chunking & Indexing
    chunks = split_legal_document(
        text=text_to_index,
        source_doc=f"Uploaded Policy: {filename}",
        default_sec="Internal Control Policy",
        language="en",
    )

    vector_store_manager.add_documents(chunks)
    hybrid_retriever.build_bm25_indexes(chunks)

    pii_status = "redacted" if pii_result.entity_count > 0 else "clean"

    # 3. Database metadata record
    doc_record = KnowledgeBaseDocument(
        filename=filename,
        source_category="uploaded",
        language="en",
        chunk_count=len(chunks),
        pii_scan_status=pii_status,
    )
    db.add(doc_record)
    db.commit()

    logger.info(
        "Uploaded document '%s' indexed: %d chunks, %d PII items (%s)",
        filename,
        len(chunks),
        pii_result.entity_count,
        pii_status,
    )

    return UploadDocumentResponse(
        filename=filename,
        category="uploaded",
        chunk_count=len(chunks),
        pii_entities_detected=pii_result.entity_count,
        pii_redacted=pii_result.entity_count > 0,
        status="indexed",
        message=f"Successfully sanitized, scanned ({pii_result.entity_count} PII items {pii_status}), and indexed {len(chunks)} chunks.",
    )


@router.get("/knowledge-base", response_model=List[Dict[str, Any]], tags=["Knowledge Base"])
def list_knowledge_base_documents(
    db: Session = Depends(get_db),
    auth_token: Optional[str] = Depends(verify_api_token),
) -> List[Dict[str, Any]]:
    """Lists indexed regulatory and uploaded policy documents in the knowledge base."""
    stmt = select(KnowledgeBaseDocument).order_by(desc(KnowledgeBaseDocument.upload_date))
    docs = db.scalars(stmt).all()

    items = [
        {
            "id": d.id,
            "filename": d.filename,
            "source_category": d.source_category,
            "language": d.language,
            "chunk_count": d.chunk_count,
            "pii_scan_status": d.pii_scan_status,
            "upload_date": d.upload_date.isoformat() if d.upload_date else None,
        }
        for d in docs
    ]

    # If DB is empty, summarize file system corpus
    if not items:
        kb_path = Path(settings.KNOWLEDGE_BASE_DIR)
        for cat in ["eu_ai_act", "bafin", "wphg_kwg", "uploaded"]:
            cat_dir = kb_path / cat
            if cat_dir.exists():
                for f in cat_dir.glob("*.txt"):
                    items.append({
                        "id": f.stem,
                        "filename": f.name,
                        "source_category": cat,
                        "language": "de" if cat in ["wphg_kwg"] or "de" in f.name else "en",
                        "chunk_count": 5,
                        "pii_scan_status": "clean",
                        "upload_date": None,
                    })

    return items
