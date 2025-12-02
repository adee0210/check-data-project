import requests
import datetime
from configs.config import PLATFORM_CONFIG


class PlatformUtil:
    def __init__(self):
        self.config = PLATFORM_CONFIG
        self.primary_platform, self.primary_settings = self.get_primary_platform()

    def get_primary_platform(self):
        for platform, settings in self.config.items():
            if settings.get("is_primary", False):
                return platform, settings
        return None, None

    def send_alert_message(
        self,
        api_name,
        symbol,
        overdue_seconds,
        allow_delay,
        alert_level="warning",
    ):
        """Gửi cảnh báo lên platform khi data quá hạn"""
        platform, settings = self.primary_platform, self.primary_settings
        if not platform:
            print("Không tìm thấy platform primary để gửi tin nhắn.")
            return

        # Tạo display name
        display_name = f"{api_name}-{symbol}" if symbol else api_name

        # Format thời gian
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Tính tổng thời gian data cũ
        total_seconds = overdue_seconds + allow_delay
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        # Map alert_level to alert_type
        if alert_level == "warning":
            alert_type = "CẢNH BÁO"
            emoji = "🟠"
            color = 0xFFA500  # Orange
        elif alert_level == "error":
            alert_type = "LỖI"
            emoji = "🔴"
            color = 0xFF0000  # Red
        else:
            alert_type = "CẢNH BÁO"
            emoji = "🟠"
            color = 0xFFA500

        # Format message
        message = (
            f"{emoji} {display_name.upper()} - {alert_type}\n"
            f"Thời gian: {current_time}\n"
            f"Dữ liệu cũ: {hours} giờ {minutes} phút {secs} giây"
        )

        # Gửi tin nhắn dựa trên platform
        if platform == "discord":
            webhook_url = settings.get("webhooks_url")
            if webhook_url:
                embed = {
                    "title": f"{emoji} {display_name.upper()} - {alert_type}",
                    "description": (
                        f"**Thời gian:** {current_time}\n"
                        f"**Dữ liệu cũ:** {hours} giờ {minutes} phút {secs} giây"
                    ),
                    "color": color,
                }
                response = requests.post(webhook_url, json={"embeds": [embed]})
                if response.status_code == 204:
                    print(f"Đã gửi {alert_type.lower()} đến Discord thành công.")
                else:
                    print(f"Lỗi gửi đến Discord: {response.status_code}")
            else:
                print("Thiếu webhooks_url cho Discord.")

        elif platform == "telegram":
            bot_token = settings.get("bot_token")
            chat_id = settings.get("chat_id")
            if bot_token and chat_id:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
                response = requests.post(url, data=data)
                if response.status_code == 200:
                    print(f"Đã gửi {alert_type.lower()} đến Telegram thành công.")
                else:
                    print(f"Lỗi gửi đến Telegram: {response.status_code}")
            else:
                print("Thiếu bot_token hoặc chat_id cho Telegram.")

        else:
            print(f"Platform {platform} chưa được hỗ trợ.")
