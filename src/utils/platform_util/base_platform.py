"""Base Platform Notifier - Interface chung cho tất cả platform notifiers"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class BasePlatformNotifier(ABC):
    """
    Abstract base class cho tất cả platform notifiers

    Các subclass phải implement:
    - send_alert(): Gửi alert message
    - validate_config(): Validate config
    - format_message(): Format message theo platform
    """

    def __init__(self, config, logger):
        """
        Initialize base notifier

        Args:
            config: Platform config (webhook, token, etc.)
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.validate_config()

    @abstractmethod
    def send_alert(
        self,
        api_name,
        symbol,
        overdue_seconds,
        allow_delay,
        check_frequency,
        alert_frequency,
        alert_level="warning",
        error_message="Không có dữ liệu mới",
        error_type: Optional[str] = None,
        source_info: Optional[Dict[str, Any]] = None,
        status_message: Optional[str] = None,
    ):
        """
        Gửi alert message

        Args:
            api_name: Tên nguồn data (API/DB/Disk)
            symbol: Optional symbol
            overdue_seconds: Số giây data đã cũ (vượt allow_delay)
            allow_delay: Ngưỡng cho phép (giây)
            check_frequency: Tần suất check (giây)
            alert_frequency: Tần suất alert (giây)
            alert_level: "warning" hoặc "error"
            error_message: Nội dung lỗi
            error_type: "API", "DATABASE", "DISK"
            source_info: Dict chứa thông tin nguồn {
                "type": "API"|"DATABASE"|"DISK",
                "url": "..." (nếu API),
                "database": "..." (nếu DATABASE),
                "collection": "..." (nếu MongoDB),
                "table": "..." (nếu PostgreSQL),
                "file_path": "..." (nếu DISK)
            }
            status_message: Optional thông báo trạng thái đặc biệt (vd: "Data quá cũ, dừng kiểm tra")

        Returns:
            True nếu gửi thành công, False nếu thất bại
        """
        pass

    @abstractmethod
    def validate_config(self):
        """
        Validate platform config

        Raises:
            ValueError: Nếu config không hợp lệ
        """
        pass

    @abstractmethod
    def get_platform_name(self):
        """
        Trả về tên platform

        Returns:
            Platform name (e.g., "Discord", "Telegram")
        """
        pass

    def format_time(self, seconds: int):
        """
        Format seconds thành "X giờ Y phút Z giây"

        Args:
            seconds: Số giây

        Returns:
            Formatted string
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours} giờ {minutes} phút {secs} giây"

    def get_alert_emoji_and_color(self, alert_level):
        """
        Get emoji và color code theo alert level

        Args:
            alert_level: "info", "warning" hoặc "error"

        Returns:
            Tuple (emoji, color_code)
        """
        if alert_level == "error":
            return "🔴", 0xFF0000  # Red
        elif alert_level == "info":
            return "🟢", 0x00FF00  # Green
        else:  # warning
            return "🟠", 0xFFA500  # Orange

    def build_base_message_data(
        self,
        api_name: str,
        symbol: Optional[str],
        overdue_seconds: int,
        allow_delay: int,
        check_frequency: int,
        alert_frequency: int,
        alert_level: str,
        error_message: str,
        error_type: Optional[str],
        source_info: Optional[Dict[str, Any]] = None,
        status_message: Optional[str] = None,
    ):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        next_time = datetime.now()
        from datetime import timedelta

        next_time = (datetime.now() + timedelta(seconds=alert_frequency)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        total_seconds = overdue_seconds + allow_delay

        emoji, color = self.get_alert_emoji_and_color(alert_level)

        # Xác định source type và details
        source_type = (
            source_info.get("type", "")
            if source_info
            else (error_type if error_type else "")
        )

        source_details = ""
        if source_info:
            if source_type == "API" and "url" in source_info:
                source_details = f"URL: {source_info['url']}"
            elif source_type == "DATABASE":
                db_type = source_info.get("database_type", "Database").upper()
                if "database" in source_info:
                    db = source_info["database"]
                    if "collection" in source_info:
                        source_details = f"Type: {db_type}\nDatabase: {db}\nCollection: {source_info['collection']}"
                    elif "table" in source_info:
                        source_details = f"Type: {db_type}\nDatabase: {db}\nTable: {source_info['table']}"
                    else:
                        source_details = f"Type: {db_type}\nDatabase: {db}"
            elif source_type == "DISK" and "file_path" in source_info:
                source_details = f"File: {source_info['file_path']}"
            elif source_type == "SYSTEM" and "message" in source_info:
                source_details = f"System: {source_info['message']}"

        # Determine alert type text with source type
        if source_type:
            alert_type = f"{api_name} - {source_type} - {'LỖI' if alert_level == 'error' else 'CẢNH BÁO'}"
        elif alert_level == "error" and error_type:
            alert_type = f"LỖI {error_type}"
        elif alert_level == "error":
            alert_type = "LỖI"
        else:
            alert_type = "CẢNH BÁO"

        return {
            "api_name": api_name,
            "symbol": symbol,
            "display_name": f"{api_name}-{symbol}" if symbol else api_name,
            "current_time": current_time,
            "next_time": next_time,
            "total_seconds": total_seconds,
            "total_time_formatted": self.format_time(total_seconds),
            "allow_delay": allow_delay,
            "allow_delay_formatted": self.format_time(allow_delay),
            "check_frequency": check_frequency,
            "alert_frequency": alert_frequency,
            "error_message": error_message,
            "alert_level": alert_level,
            "alert_type": alert_type,
            "emoji": emoji,
            "color": color,
            "source_type": source_type,
            "source_details": source_details,
            "status_message": status_message,
        }

    def is_enabled(self):
        """
        Check xem platform có được enable không

        Returns:
            True nếu is_primary=True trong config
        """
        return self.config.get("is_primary", False)
