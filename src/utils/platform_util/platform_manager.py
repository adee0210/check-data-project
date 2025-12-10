"""Platform Manager - Quản lý tập trung tất cả platform notifiers"""

from typing import Dict, Any, Optional, List
from configs.logging_config import LoggerConfig
from utils.platform_util.base_platform import BasePlatformNotifier
from utils.platform_util.discord_util import DiscordNotifier
from utils.platform_util.telegram_util import TelegramNotifier


class PlatformManager:
    """
    Platform Manager - Quản lý tất cả platform notifiers

    Tính năng:
    - Tự động reload config từ common_config.json
    - Factory pattern để tạo notifiers
    - Hỗ trợ nhiều primary platforms
    - Dễ dàng mở rộng với platforms mới

    Sử dụng:
        manager = PlatformManager()

        # Gửi alert
        manager.send_alert("api_name", "BTC", ...)

        # Gửi đến platform cụ thể
        manager.send_to_discord("message")
        manager.send_to_telegram("message")
    """

    # Registry của các platforms hỗ trợ
    NOTIFIER_REGISTRY = {
        "discord": DiscordNotifier,
        "telegram": TelegramNotifier,
        # "email": EmailNotifier,
        # "sms": SMSNotifier,
    }

    def __init__(self):
        """
        Initialize Platform Manager
        """
        self.logger = LoggerConfig.logger_config("PlatformManager")
        self.notifiers: Dict[str, BasePlatformNotifier] = {}
        self._load_notifiers()

    def _load_platform_config(self) -> Dict[str, Any]:
        """
        Load platform config từ common_config.json

        Returns:
            Dict platform config
        """
        from utils.load_config_util import LoadConfigUtil

        config = LoadConfigUtil.load_json_to_variable("common_config.json")
        return config.get("PLATFORM_CONFIG", {})

    def _create_notifier(
        self, platform_name: str, config: Dict[str, Any]
    ) -> Optional[BasePlatformNotifier]:
        """
        Factory method: Tạo notifier instance theo platform

        Args:
            platform_name: Platform name ("discord", "telegram", etc.)
            config: Platform config

        Returns:
            BasePlatformNotifier instance hoặc None nếu không hỗ trợ
        """
        notifier_class = self.NOTIFIER_REGISTRY.get(platform_name.lower())

        if not notifier_class:
            self.logger.warning(
                f"Platform '{platform_name}' không được hỗ trợ. "
                f"Các platform hỗ trợ: {', '.join(self.NOTIFIER_REGISTRY.keys())}"
            )
            return None

        try:
            return notifier_class(config, self.logger)
        except ValueError as e:
            self.logger.error(f"Lỗi validate config cho {platform_name}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Lỗi tạo notifier cho {platform_name}: {str(e)}")
            return None

    def _load_notifiers(self) -> None:
        """
        Load tất cả platform notifiers từ config
        """
        platform_config = self._load_platform_config()

        for platform_name, config in platform_config.items():
            notifier = self._create_notifier(platform_name, config)
            if notifier:
                self.notifiers[platform_name] = notifier

                if notifier.is_enabled():
                    self.logger.info(f"Đã load {platform_name} notifier (PRIMARY)")
                else:
                    self.logger.info(f"Đã load {platform_name} notifier (disabled)")

    def reload_config(self) -> None:
        """
        Reload platform config và recreate notifiers

        Useful khi config thay đổi trong runtime
        """
        self.notifiers.clear()
        self._load_notifiers()
        self.logger.info("Đã reload platform config")

    def get_primary_platforms(self) -> List[str]:
        """
        Lấy danh sách platforms có is_primary=True

        Returns:
            List of primary platform names
        """
        primary = []
        for name, notifier in self.notifiers.items():
            if notifier.is_enabled():
                primary.append(name)
        return primary

    def send_alert(
        self,
        api_name: str,
        symbol: Optional[str] = None,
        overdue_seconds: int = 0,
        allow_delay: int = 60,
        check_frequency: int = 10,
        alert_frequency: int = 60,
        alert_level: str = "warning",
        error_message: str = "Không có dữ liệu mới",
        error_type: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        Gửi alert đến TẤT CẢ primary platforms

        Args:
            api_name: Tên API (vd: "gold-data", "cmc")
            symbol: Symbol nếu có (vd: "BTC", "ETH")
            overdue_seconds: Số giây data quá hạn
            allow_delay: Ngưỡng cho phép delay (giây)
            check_frequency: Tần suất check (giây)
            alert_frequency: Tần suất gửi alert (giây)
            alert_level: Mức độ alert ("info", "warning", "error")
            error_message: Message mô tả lỗi
            error_type: Loại lỗi ("API", "Database", etc.)

        Returns:
            Dict {platform_name: success_status}
        """
        # Reload config mỗi lần gọi để đảm bảo up-to-date
        # (Low overhead vì LoadConfigUtil có caching)
        self.reload_config()

        results = {}
        primary_platforms = self.get_primary_platforms()

        if not primary_platforms:
            self.logger.warning("Không có platform primary nào để gửi alert")
            return results

        for platform_name in primary_platforms:
            notifier = self.notifiers[platform_name]

            try:
                success = notifier.send_alert(
                    api_name,
                    symbol,
                    overdue_seconds,
                    allow_delay,
                    check_frequency,
                    alert_frequency,
                    alert_level,
                    error_message,
                    error_type,
                )
                results[platform_name] = success

            except Exception as e:
                self.logger.error(f"Lỗi gửi alert qua {platform_name}: {str(e)}")
                results[platform_name] = False

        return results

    def send_to_specific_platform(
        self,
        platform_name: str,
        api_name: str,
        symbol: Optional[str],
        overdue_seconds: int,
        allow_delay: int,
        check_frequency: int,
        alert_frequency: int,
        alert_level: str = "warning",
        error_message: str = "Không có dữ liệu mới",
        error_type: Optional[str] = None,
    ) -> bool:
        """
        Gửi alert đến 1 platform cụ thể (bỏ qua is_primary)

        Args:
            platform_name: Platform name ("discord", "telegram", etc.)
            Các args khác: Xem send_alert()

        Returns:
            True nếu gửi thành công
        """
        if platform_name not in self.notifiers:
            self.logger.error(f"Platform '{platform_name}' không tồn tại")
            return False

        notifier = self.notifiers[platform_name]

        try:
            return notifier.send_alert(
                api_name,
                symbol,
                overdue_seconds,
                allow_delay,
                check_frequency,
                alert_frequency,
                alert_level,
                error_message,
                error_type,
            )
        except Exception as e:
            self.logger.error(f"Lỗi gửi alert qua {platform_name}: {str(e)}")
            return False

    def send_holiday_alert(self, message: str) -> Dict[str, bool]:
        """
        Gửi holiday alert đến tất cả primary platforms

        Args:
            message: Holiday alert message

        Returns:
            Dict {platform_name: success_status}
        """
        results = {}
        primary_platforms = self.get_primary_platforms()

        for platform_name in primary_platforms:
            notifier = self.notifiers[platform_name]

            if hasattr(notifier, "send_holiday_alert"):
                try:
                    success = notifier.send_holiday_alert(message)
                    results[platform_name] = success
                except Exception as e:
                    self.logger.error(
                        f"Lỗi gửi holiday alert qua {platform_name}: {str(e)}"
                    )
                    results[platform_name] = False

        return results

    def list_supported_platforms(self) -> List[str]:
        """
        Liệt kê các platforms được hỗ trợ

        Returns:
            List of supported platform names
        """
        return list(self.NOTIFIER_REGISTRY.keys())

    def list_loaded_platforms(self) -> List[str]:
        """
        Liệt kê các platforms đã được load

        Returns:
            List of loaded platform names
        """
        return list(self.notifiers.keys())
