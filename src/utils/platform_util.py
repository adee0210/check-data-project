import json
import requests
import datetime
import os


class PlatformUtil:
    def __init__(self):
        self.config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "configs",
            "platform_config.json",
        )
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.primary_platform, self.primary_settings = self.get_primary_platform()

    def get_primary_platform(self):
        for platform, settings in self.config.items():
            if settings.get("is_primary", False):
                return platform, settings
        return None, None

    def send_alert_message(
        self,
        data_name,
        datetime_str,
        symbols,
        no_data_seconds,
        check_frequency,
        alert_frequency,
        alert_level="warning",
    ):
        platform, settings = self.primary_platform, self.primary_settings
        if not platform:
            print("Không tìm thấy platform primary để gửi tin nhắn.")
            return

        # Format symbols
        symbols_str = ", ".join(symbols) if symbols else "N/A"

        # Tính thời gian gửi message tiếp theo
        next_time = datetime.datetime.now() + datetime.timedelta(
            seconds=alert_frequency
        )
        next_time_str = next_time.strftime("%Y-%m-%d %H:%M:%S")

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
            f"{emoji} {data_name.upper()} - {alert_type}\n"
            f"Thời gian: {datetime_str}\n"
            f"Symbol: {symbols_str}\n"
            f"Số giây không có dữ liệu mới: {no_data_seconds} giây\n"
            f"Tần suất kiểm tra: {check_frequency} giây\n"
            f"Thời gian gửi message tiếp theo: {next_time_str}"
        )

        # Gửi tin nhắn dựa trên platform
        if platform == "discord":
            webhook_url = settings.get("webhooks_url")
            if webhook_url:
                embed = {
                    "title": f"{emoji} {data_name.upper()} - {alert_type}",
                    "description": (
                        f"**Thời gian:** {datetime_str}\n"
                        f"**Symbol:** {symbols_str}\n"
                        f"**Số giây không có dữ liệu mới:** {no_data_seconds} giây\n"
                        f"**Tần suất kiểm tra:** {check_frequency} giây\n"
                        f"**Thời gian gửi message tiếp theo:** {next_time_str}"
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
