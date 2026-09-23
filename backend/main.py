"""KonformAI FastAPI application root entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_classification import router as classification_router
from backend.api.routes_health import router as health_router
from backend.api.routes_knowledge_base import router as kb_router
from backend.api.routes_review import router as review_router
from backend.core.config import settings
from backend.core.logging_config import setup_logging
from backend.db.session import init_db
from backend.observability.langsmith_config import init_langsmith
from backend.observability.otel_config import setup_opentelemetry
from backend.rag.ingestion import ingest_all_documents

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown event handler."""
    # 1. Structured Logging
    setup_logging()
    logger.info("Initializing %s backend services...", settings.PROJECT_NAME)

    # 2. Database schema initialization
    init_db()

    # 3. Observability & Tracing setup
    init_langsmith()
    setup_opentelemetry(app)

    # 4. Regulatory Knowledge Base warm-up
    try:
        ingest_all_documents()
        logger.info("Knowledge base corpus verified and hybrid indexes ready.")
    except Exception as exc:
        logger.warning("Knowledge base warm-up notice (%s); will load on-demand.", exc)

    logger.info("%s API server startup complete.", settings.PROJECT_NAME)
    yield
    logger.info("Shutting down %s backend services.", settings.PROJECT_NAME)


app = FastAPI(
    title=f"{settings.PROJECT_NAME} Compliance Engine",
    description="Agentic EU AI Act & BaFin Compliance Classification API for German Financial Institutions",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers under /api/v1
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(classification_router, prefix=settings.API_V1_STR)
app.include_router(review_router, prefix=settings.API_V1_STR)
app.include_router(kb_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root_status():
    """Root status greeting."""
    return {
        "service": settings.PROJECT_NAME,
        "description": "Agentic AI Act & BaFin Compliance Classifier",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
