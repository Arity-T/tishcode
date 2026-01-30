import logging
import os

from agno.models.openai import OpenAIChat


logger = logging.getLogger("tishcode")


def create_openai_model() -> OpenAIChat:
    """Create OpenAI model with validation of environment variables."""
    model_id = os.getenv("TC_OPENAI_MODEL")
    api_key = os.getenv("TC_OPENAI_API_KEY")
    base_url = os.getenv("TC_OPENAI_BASE_URL")

    if not model_id:
        raise ValueError("TC_OPENAI_MODEL environment variable is not set")
    if not api_key:
        raise ValueError("TC_OPENAI_API_KEY environment variable is not set")
    if not base_url:
        raise ValueError("TC_OPENAI_BASE_URL environment variable is not set")

    logger.info(f"Using model: {model_id}, base_url: {base_url}")

    return OpenAIChat(
        id=model_id,
        api_key=api_key,
        base_url=base_url,
    )
