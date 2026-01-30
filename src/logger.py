import logging
import os


def setup_logger() -> logging.Logger:
    """Configure and return logger with level from environment."""
    log_level = os.getenv("TC_LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    logger = logging.getLogger("tishcode")
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    return logging.getLogger("tishcode")
