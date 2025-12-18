import glob
import json
import os
from configs.logging_config import LoggerConfig


class LoadConfigUtil:
    """Utility để load config từ file JSON"""

    _logger = None

    @staticmethod
    def _get_logger():
        """Lazy load logger"""
        if LoadConfigUtil._logger is None:
            LoadConfigUtil._logger = LoggerConfig.logger_config("LoadConfigUtil")
        return LoadConfigUtil._logger

    @staticmethod
    def load_json_to_variable(filename, config_type=None):
        """
        Tìm và load file JSON, trả về config theo type hoặc toàn bộ file

        Args:
            filename: Tên file JSON (vd: "api_config.json", "database_config.json")
            config_type: (Optional) Loại config muốn lấy. Nếu None, trả về toàn bộ file

        Returns:
            Dict config theo type yêu cầu hoặc toàn bộ config
        """
        # Tìm file
        files = glob.glob(f"**/{filename}", recursive=True)
        if not files:
            raise FileNotFoundError(f"Không tìm thấy file: {filename}")

        file_path = files[0]

        # Luôn load từ file
        with open(file=file_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        # Nếu có config_type, lấy theo type
        if config_type:
            if config_type not in data:
                raise KeyError(f"Không tìm thấy '{config_type}' trong file {filename}")
            result = data[config_type]
        else:
            # Không có config_type, trả về toàn bộ
            result = data

        # Log load
        logger = LoadConfigUtil._get_logger()
        config_desc = f" [{config_type}]" if config_type else ""
        logger.info(f"Đã load config: {filename}{config_desc}")

        return result

    @staticmethod
    def get_all_configs(filename):
        """
        Load toàn bộ config từ file JSON

        Args:
            filename: Tên file JSON

        Returns:
            Dict chứa tất cả config
        """
        files = glob.glob(f"**/{filename}", recursive=True)
        if not files:
            raise FileNotFoundError(f"Không tìm thấy file: {filename}")

        file_path = files[0]

        with open(file=file_path, mode="r", encoding="utf-8") as f:
            return json.load(f)
