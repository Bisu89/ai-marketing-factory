import logging
import sys

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(handler)
