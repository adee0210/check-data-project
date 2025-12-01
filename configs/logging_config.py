import logging
import os
import sys
from logging.handlers import RotatingFileHandler


class LoggerConfig:

    @staticmethod
    def logger_config(
        log_name: str, log_file: str = "main.log", log_level: int = logging.INFO
    ):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_path = os.path.join(root_dir, "logs", log_file)

        # Tạo thư mục logs nếu chưa tồn tại
        os.makedirs(os.path.dirname(base_path), exist_ok=True)

        # formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(processName)s - %(levelname)s - %(name)s - %(message)s"
        )

        file_handler = RotatingFileHandler(
            filename=base_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        logger = logging.getLogger(log_name)

        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        logger.propagate = False
        logger.setLevel(log_level)
        return logger
