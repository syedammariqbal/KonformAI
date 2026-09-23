"""Database engine, session factory, and FastAPI dependency."""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings
from backend.db.models import Base

logger = logging.getLogger(__name__)

import socket


def _is_port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_engine():
    database_url = settings.DATABASE_URL
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})

    # Parse host & port if present
    host = "localhost"
    port = 5432
    if "@" in database_url:
        host_port = database_url.split("@")[-1].split("/")[0]
        if ":" in host_port:
            parts = host_port.split(":")
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                port = 5432
        else:
            host = host_port

    if not _is_port_open(host, port, timeout=0.3):
        logger.info(
            "PostgreSQL port %s:%d is not open. Falling back to local SQLite: 'sqlite:///./konformai.db'",
            host,
            port,
        )
        return create_engine("sqlite:///./konformai.db", connect_args={"check_same_thread": False})

    try:
        pg_engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        return pg_engine
    except Exception as exc:
        logger.warning(
            "Could not initialize PostgreSQL engine (%s). Falling back to SQLite: 'sqlite:///./konformai.db'",
            exc,
        )
        return create_engine("sqlite:///./konformai.db", connect_args={"check_same_thread": False})


engine = _get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initializes tables in database schema if not present."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.warning("Database schema initialization warning (will retry or use migrations): %s", e)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
