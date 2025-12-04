import glob
import json
import os


class LoadConfigUtil:
    """Utility để load config từ file JSON động"""

    _cache = {}
    _last_modified = {}

    @staticmethod
    def load_json_to_variable(filename, config_type):
        """
        Tìm và load file JSON, trả về config theo type

        Args:
            filename: Tên file JSON (vd: "config.json")
            config_type: Loại config muốn lấy (vd: "API_CONFIG", "DATABASE_CONFIG")

        Returns:
            Dict config theo type yêu cầu
        """
        # Tìm file
        files = glob.glob(f"**/{filename}", recursive=True)
        if not files:
            raise FileNotFoundError(f"Không tìm thấy file: {filename}")

        file_path = files[0]

        # Kiểm tra file có thay đổi không (để reload)
        current_mtime = os.path.getmtime(file_path)
        cache_key = f"{file_path}:{config_type}"

        if cache_key in LoadConfigUtil._cache:
            if LoadConfigUtil._last_modified.get(cache_key) == current_mtime:
                # File không thay đổi, dùng cache
                return LoadConfigUtil._cache[cache_key]

        # Load file mới hoặc file đã thay đổi
        with open(file=file_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        if config_type not in data:
            raise KeyError(f"Không tìm thấy '{config_type}' trong file {filename}")

        # Cache lại
        LoadConfigUtil._cache[cache_key] = data[config_type]
        LoadConfigUtil._last_modified[cache_key] = current_mtime

        return data[config_type]

    @staticmethod
    def reload_config(filename, config_type):
        """
        Force reload config từ file (bỏ qua cache)

        Args:
            filename: Tên file JSON
            config_type: Loại config muốn reload

        Returns:
            Dict config mới
        """
        files = glob.glob(f"**/{filename}", recursive=True)
        if not files:
            raise FileNotFoundError(f"Không tìm thấy file: {filename}")

        file_path = files[0]
        cache_key = f"{file_path}:{config_type}"

        # Xóa cache
        if cache_key in LoadConfigUtil._cache:
            del LoadConfigUtil._cache[cache_key]
        if cache_key in LoadConfigUtil._last_modified:
            del LoadConfigUtil._last_modified[cache_key]

        # Load lại
        return LoadConfigUtil.load_json_to_variable(filename, config_type)

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
