from datetime import datetime, timedelta


class DataValidator:
    """Xử lý logic kiểm tra dữ liệu hợp lệ"""

    @staticmethod
    def is_data_fresh(data_datetime: datetime, allow_delay):
        """
        Kiểm tra xem dữ liệu có còn mới không (dựa vào allow_delay)

        Logic: So sánh data_datetime với time_threshold (current_time - allow_delay)
        - Nếu data_datetime >= time_threshold → FRESH (trong thời gian cho phép)
        - Nếu data_datetime < time_threshold → OVERDUE (quá hạn)

        Returns:
            tuple: (is_fresh, overdue_seconds)
        """
        current_time = datetime.now()
        time_threshold = current_time - timedelta(seconds=allow_delay)

        if data_datetime >= time_threshold:
            return True, 0
        else:
            overdue_seconds = int(
                (current_time - data_datetime).total_seconds() - allow_delay
            )
            return False, overdue_seconds

    @staticmethod
    def format_time_overdue(seconds, allow_delay_seconds):
        """
        Chuyển đổi số giây quá hạn sang định dạng giờ phút giây
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        allow_hours = allow_delay_seconds // 3600
        allow_minutes = (allow_delay_seconds % 3600) // 60

        return f"{hours} giờ {minutes} phút {secs} giây (ngưỡng {allow_hours} giờ {allow_minutes} phút)"
