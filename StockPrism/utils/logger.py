import os
import logging
from datetime import datetime
from pathlib import Path

_LOGGING_CONFIGURED = False


def get_logger(name: str = __name__) -> logging.Logger:
    global _LOGGING_CONFIGURED

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not _LOGGING_CONFIGURED:
        formatter = logging.Formatter(
            "[%(asctime)s]: %(name)s: %(levelname)s: %(lineno)d: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Configure console handler
        console_log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        console_level = getattr(logging, console_log_level_str, logging.INFO)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Attempt file handler creation with safety fallback for read-only environments
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_dir = Path("logs") / current_date
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{current_timestamp}.log"

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as exc:
            logger.warning(f"Could not initialize file logger: {exc}. Using console logger only.")

        _LOGGING_CONFIGURED = True

    return logger
