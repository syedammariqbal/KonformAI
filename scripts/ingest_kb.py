"""CLI script to ingest the regulatory knowledge base and build hybrid indexes."""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.logging_config import setup_logging
from backend.rag.ingestion import ingest_all_documents


def main():
    parser = argparse.ArgumentParser(description="Ingest regulatory corpus for KonformAI")
    parser.add_argument(
        "--kb-dir",
        type=str,
        default=None,
        help="Path to knowledge_base directory (defaults to settings.KNOWLEDGE_BASE_DIR)",
    )
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("ingest_kb")
    logger.info("Starting regulatory corpus ingestion...")

    try:
        chunks = ingest_all_documents(kb_dir=args.kb_dir)
        logger.info("Successfully ingested and indexed %d regulatory chunks.", len(chunks))
    except Exception as e:
        logger.exception("Ingestion failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
