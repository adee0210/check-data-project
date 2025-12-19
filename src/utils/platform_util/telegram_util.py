"""Telegram Notifier - Gửi alert qua Telegram Bot API"""

import requests
from typing import Dict, Any, Optional
from utils.platform_util.base_platform import BasePlatformNotifier


class TelegramNotifier(BasePlatformNotifier):
    """
    Telegram notifier implementation

    Sử dụng Telegram Bot API để gửi messages
    """

    def validate_config(self) -> None:
        """
        Validate Telegram config

        Raises:
            ValueError: Nếu thiếu bot_token hoặc chat_id
        """
        if not self.config.get("bot_token"):
            raise ValueError("Thiếu 'bot_token' trong Telegram config")

        if not self.config.get("chat_id"):
            raise ValueError("Thiếu 'chat_id' trong Telegram config")

    def get_platform_name(self) -> str:
        """
        Trả về tên platform

        Returns:
            "Telegram"
        """
        return "Telegram"

    def send_alert(
        self,
        api_name: str,
        symbol: Optional[str],
        overdue_seconds: int,
        allow_delay: int,
        check_frequency: int,
        alert_frequency: int,
        alert_level: str = "warning",
        error_message: str = "Không có dữ liệu mới",
        error_type: Optional[str] = None,
        source_info: Optional[Dict[str, Any]] = None,
        status_message: Optional[str] = None,
    ) -> bool:
        """
        Gửi alert đến Telegram qua Bot API

        Args:
            Xem BasePlatformNotifier.send_alert() docstring

        Returns:
            True nếu gửi thành công (status 200), False nếu thất bại
        """
        if not self.is_enabled():
            self.logger.debug("Telegram notifier không được enable")
            return False

        bot_token = self.config["bot_token"]
        chat_id = self.config["chat_id"]

        # Build message data
        data = self.build_base_message_data(
            api_name,
            symbol,
            overdue_seconds,
            allow_delay,
            check_frequency,
            alert_frequency,
            alert_level,
            error_message,
            error_type,
            source_info,
            status_message,
        )

        # Format Telegram message
        message = self._format_telegram_message(data)

        # Telegram Bot API endpoint
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",  # Support bold, italic, etc.
        }

        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                self.logger.info(
                    f"Đã gửi {data['alert_type'].lower()} đến Telegram thành công"
                )
                return True
            else:
                self.logger.error(f"Lỗi gửi đến Telegram: HTTP {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Timeout khi gửi đến Telegram")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi gửi đến Telegram: {str(e)}")
            return False

    def _format_telegram_message(self, data: Dict[str, Any]) -> str:
        """
        Format message thành Telegram Markdown

        Args:
            data: Message data từ build_base_message_data()

        Returns:
            Formatted Markdown string
        """
        message_parts = [
            f"{data['emoji']} *{data['alert_type']}*\n",
            f"*Nội dung:* {data['error_message']}",
            f"*Thời gian:* {data['current_time']}",
        ]

        # Thêm source details ngay sau thời gian nếu có
        if data.get("source_details"):
            message_parts.append(f"*{data['source_details']}*")

        # Thêm symbol nếu có
        if data["symbol"]:
            message_parts.append(f"*Symbol:* {data['symbol']}")

        # Thêm các field còn lại
        message_parts.extend(
            [
                f"*Ngưỡng cho phép:* {data['allow_delay_formatted']}",
                f"*Tần suất kiểm tra:* {data['check_frequency']} giây",
                f"*Thời gian gửi message tiếp theo (nếu còn lỗi):* {data['next_time']}",
            ]
        )

        # Thêm status_message nếu có (hiển thị rõ ràng)
        if data.get("status_message"):
            message_parts.append(f"\n*Trạng thái:* {data['status_message']}")

        message = "\n".join(message_parts)

        return message

    def send_holiday_alert(self, message: str) -> bool:
        """
        Gửi alert đặc biệt cho holiday detection

        Args:
            message: Holiday alert message

        Returns:
            True nếu gửi thành công
        """
        # Holiday alerts disabled — method retained for compatibility
        self.logger.debug(
            "Holiday alert disabled in Telegram notifier; ignoring request"
        )
        return False
