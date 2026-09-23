"""LangSmith tracing configuration and URL helper."""

import logging
import os

from backend.core.config import settings

logger = logging.getLogger(__name__)


def init_langsmith() -> None:
    """Configures LangSmith environment variables for automated LangChain/LangGraph tracing.

    Auto-disables tracing if LANGCHAIN_API_KEY is empty to prevent 401 errors.
    """
    api_key = (settings.LANGCHAIN_API_KEY or "").strip()

    if settings.LANGCHAIN_TRACING_V2 and api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        os.environ["LANGCHAIN_API_KEY"] = api_key
        logger.info("LangSmith tracing enabled for project: %s", settings.LANGCHAIN_PROJECT)
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        if settings.LANGCHAIN_TRACING_V2 and not api_key:
            logger.warning(
                "LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY is empty — "
                "tracing auto-disabled. Get a free key at https://smith.langchain.com "
                "or set LANGCHAIN_TRACING_V2=false in .env to silence this warning."
            )


def get_langsmith_project_url() -> str:
    """Returns the web dashboard URL for inspecting traces in LangSmith."""
    project = settings.LANGCHAIN_PROJECT or "konformai"
    return f"https://smith.langchain.com/o/default/projects/p/{project}"
