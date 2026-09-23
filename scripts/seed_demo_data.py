"""Seeds synthetic demo AI systems into the database for immediate testing and presentation."""

import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.logging_config import setup_logging
from backend.db.models import Case
from backend.db.session import SessionLocal, init_db
from backend.observability.audit_logger import log_audit_event

logger = logging.getLogger("seed_demo_data")


def seed_demo_cases():
    setup_logging()
    init_db()
    logger.info("Seeding synthetic demo AI systems...")

    sample_dir = ROOT_DIR / "data" / "sample_systems"
    sample_files = list(sample_dir.glob("*.json"))

    if not sample_files:
        logger.warning("No sample files located in %s", sample_dir)
        return

    with SessionLocal() as db:
        for fpath in sample_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                existing = db.query(Case).filter(Case.system_name == data["system_name"]).first()
                if existing:
                    logger.info("Case '%s' already exists in database.", data["system_name"])
                    continue

                is_prohib = data.get("expected_risk_tier") == "prohibited"
                case = Case(
                    system_name=data["system_name"],
                    system_description=data["system_description"],
                    status="completed" if not is_prohib else "awaiting_human_review",
                    risk_tier=data.get("expected_risk_tier"),
                    confidence_score=0.95,
                    is_prohibited_practice=is_prohib,
                    structured_intake={
                        "system_purpose": data["system_name"],
                        "sector": data.get("sector", "Banking"),
                        "autonomy_level": "Semi-automated",
                    },
                )
                db.add(case)
                db.commit()
                db.refresh(case)

                log_audit_event(
                    db=db,
                    case_id=case.id,
                    event_type="DEMO_CASE_SEEDED",
                    actor="seed_script",
                    details={"file": fpath.name, "expected_tier": data.get("expected_risk_tier")},
                )
                logger.info("Seeded demo case '%s' (ID: %s)", data["system_name"], case.id)

            except Exception as e:
                logger.error("Failed to seed file %s: %s", fpath.name, e)
                db.rollback()

    logger.info("Demo data seeding completed.")


if __name__ == "__main__":
    seed_demo_cases()
