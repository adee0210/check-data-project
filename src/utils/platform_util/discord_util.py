"""Discord Notifier - Gửi alert qua Discord webhook"""

import requests
from typing import Dict, Any, Optional
from utils.platform_util.base_platform import BasePlatformNotifier


class DiscordNotifier(BasePlatformNotifier):
    """
    Discord notifier implementation

    Sử dụng Discord webhook để gửi rich embed messages
    """

    def validate_config(self) -> None:
        """
        Validate Discord config

        Raises:
            ValueError: Nếu thiếu webhooks_url
        """
        if not self.config.get("webhooks_url"):
            raise ValueError("Thiếu 'webhooks_url' trong Discord config")

        # Validate webhook URL format
        webhook_url = self.config["webhooks_url"]
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            raise ValueError("Discord webhook URL không hợp lệ")

    def get_platform_name(self) -> str:
        """
        Trả về tên platform

        Returns:
            "Discord"
        """
        return "Discord"

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
        Gửi alert đến Discord qua webhook

        Args:
            Xem BasePlatformNotifier.send_alert() docstring

        Returns:
            True nếu gửi thành công (status 204), False nếu thất bại
        """
        if not self.is_enabled():
            self.logger.debug("Discord notifier không được enable")
            return False

        webhook_url = self.config["webhooks_url"]

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

        # Format Discord embed
        embed = self._format_discord_embed(data)

        try:
            response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)

            if response.status_code == 204:
                self.logger.info(
                    f"Đã gửi {data['alert_type'].lower()} đến Discord thành công"
                )
                return True
            else:
                self.logger.error(f"Lỗi gửi đến Discord: HTTP {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Timeout khi gửi đến Discord")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi gửi đến Discord: {str(e)}")
            return False

    def _format_discord_embed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format message thành Discord embed

        Args:
            data: Message data từ build_base_message_data()

        Returns:
            Discord embed dict
        """
        # Build description với Nội dung + Dữ liệu cũ ở đầu
        description_parts = [
            f"**Nội dung:** {data['error_message']} - Dữ liệu cũ: {data['total_time_formatted']}",
            f"**Thời gian:** {data['current_time']}",
        ]

        # Thêm source details ngay sau thời gian nếu có
        if data.get("source_details"):
            description_parts.append(f"**{data['source_details']}**")

        # Thêm symbol nếu có
        if data["symbol"]:
            description_parts.append(f"**Symbol:** {data['symbol']}")

        # Thêm các field còn lại
        description_parts.extend(
            [
                f"**Ngưỡng cho phép:** {data['allow_delay_formatted']}",
                f"**Tần suất kiểm tra:** {data['check_frequency']} giây",
                f"**Thời gian gửi message tiếp theo (nếu còn lỗi):** {data['next_time']}",
            ]
        )

        # Thêm status_message nếu có (hiển thị rõ ràng)
        if data.get("status_message"):
            description_parts.append(f"\n**Trạng thái:** {data['status_message']}")

        description = "\n".join(description_parts)

        embed = {
            "title": f"{data['emoji']} {data['alert_type']}",
            "description": description,
            "color": data["color"],
            "footer": {"text": "Data Monitoring System"},
            "timestamp": data["current_time"],
        }

        return embed

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
            "Holiday alert disabled in Discord notifier; ignoring request"
        )
        return False
