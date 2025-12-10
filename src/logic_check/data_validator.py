"""Module xử lý logic kiểm tra dữ liệu hợp lệ"""

from datetime import datetime, timedelta


class DataValidator:
    """Xử lý logic kiểm tra dữ liệu hợp lệ"""

    @staticmethod
    def is_data_fresh(data_datetime: datetime, allow_delay):
        """
        Kiểm tra xem dữ liệu có còn mới không (dựa vào allow_delay)

        Logic:
        - Nếu data_datetime chỉ có ngày (00:00:00): So sánh theo ngày
          Ví dụ: "2025-12-04" với allow_delay=86400 (1 ngày)
                  → Fresh nếu hôm nay là 2025-12-04 hoặc 2025-12-05
                  → Stale nếu hôm nay là 2025-12-06 trở đi

        - Nếu data_datetime có cả giờ phút: So sánh chính xác theo giây
          Ví dụ: "2025-12-04 14:30:00" với allow_delay=60 (1 phút)
                  → Fresh nếu hiện tại <= 2025-12-04 14:31:00
                  → Stale nếu hiện tại > 2025-12-04 14:31:00

        Returns:
            tuple: (is_fresh, overdue_seconds)
        """
        current_time = datetime.now()

        # Kiểm tra xem data_datetime có phải chỉ là ngày không (giờ = 00:00:00)
        is_date_only = (
            data_datetime.hour == 0
            and data_datetime.minute == 0
            and data_datetime.second == 0
        )

        if is_date_only:
            # So sánh theo ngày - sử dụng date() để bỏ phần giờ
            data_date = data_datetime.date()
            current_date = current_time.date()

            # Tính số ngày cho phép từ allow_delay (giây)
            allow_days = allow_delay / 86400  # 86400 = số giây trong 1 ngày

            # Tính ngày threshold
            threshold_date = current_date - timedelta(days=allow_days)

            if data_date >= threshold_date:
                return True, 0
            else:
                # Tính số ngày quá hạn
                days_overdue = (current_date - data_date).days - int(allow_days)
                overdue_seconds = days_overdue * 86400
                return False, overdue_seconds
        else:
            # So sánh theo giây chính xác (logic cũ cho datetime đầy đủ)
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
        Chuyển đổi số giây quá hạn sang định dạng dễ đọc

        - Nếu > 1 ngày: Hiển thị theo ngày
        - Nếu <= 1 ngày: Hiển thị theo giờ phút giây
        """
        # Tính số ngày
        days = seconds // 86400
        remaining_seconds = seconds % 86400

        # Tính allow_delay theo ngày
        allow_days = allow_delay_seconds // 86400
        allow_remaining = allow_delay_seconds % 86400

        # Nếu quá hạn >= 1 ngày, hiển thị theo ngày
        if days >= 1:
            if allow_days >= 1:
                return f"{days} ngày (ngưỡng {allow_days} ngày)"
            else:
                # allow_delay < 1 ngày nhưng overdue >= 1 ngày
                allow_hours = allow_delay_seconds // 3600
                allow_minutes = (allow_delay_seconds % 3600) // 60
                return f"{days} ngày (ngưỡng {allow_hours} giờ {allow_minutes} phút)"
        else:
            # Quá hạn < 1 ngày, hiển thị theo giờ phút giây
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            allow_hours = allow_delay_seconds // 3600
            allow_minutes = (allow_delay_seconds % 3600) // 60

            return f"{hours} giờ {minutes} phút {secs} giây (ngưỡng {allow_hours} giờ {allow_minutes} phút)"
