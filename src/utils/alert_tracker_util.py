from datetime import datetime
from typing import Dict, Optional, Set, Tuple


class AlertTracker:
    """
    Quản lý tracking cho alert của một checker

    Attributes:
        last_alert_times: Track lần alert cuối cho mỗi item
        first_stale_times: Track lần đầu tiên data bị stale
        outside_schedule_logged: Track trạng thái outside schedule
        max_stale_exceeded: Track items vượt quá max_stale_seconds
        low_activity_symbols: Set các symbol đã xác định low-activity
        consecutive_stale_days: Track số ngày liên tiếp stale
        empty_data_tracking: Track empty data warnings
        holiday_tracking: Track số lần check lỗi liên tiếp để phát hiện ngày lễ
    """

    def __init__(self):
        self.last_alert_times = {}
        self.first_stale_times = {}
        self.outside_schedule_logged = {}
        self.max_stale_exceeded = {}
        self.low_activity_symbols = set()
        self.consecutive_stale_days = {}
        self.empty_data_tracking = {}

        # Holiday detection: Track số lần gửi alert để phát hiện ngày lễ
        # Format: {display_name: {'alert_count': int, 'alert_frequency': int}}
        self.holiday_tracking = {}

        # Track timestamp của data cuối cùng để phát hiện data mới
        self.last_seen_timestamps = {}

    def should_send_alert(self, display_name, alert_frequency):
        """
        Kiểm tra xem có nên gửi alert không dựa vào alert_frequency

        Args:
            display_name: Tên hiển thị của item
            alert_frequency: Tần suất alert tối thiểu (giây)

        Returns:
            True nếu nên gửi alert, False nếu không
        """
        last_alert = self.last_alert_times.get(display_name)
        if last_alert is None:
            return True

        current_time = datetime.now()
        time_since_last_alert = (current_time - last_alert).total_seconds()
        return time_since_last_alert >= alert_frequency

    def record_alert_sent(self, display_name):
        """
        Ghi nhận đã gửi alert

        Args:
            display_name: Tên hiển thị của item
        """
        self.last_alert_times[display_name] = datetime.now()

    def is_in_silent_mode(self, display_name):
        """
        Kiểm tra xem item có đang ở silent mode không

        Args:
            display_name: Tên hiển thị của item

        Returns:
            True nếu đang ở silent mode, False nếu không
        """
        return display_name in self.max_stale_exceeded

    def is_low_activity(self, display_name):
        """
        Kiểm tra xem item có phải low-activity không

        Args:
            display_name: Tên hiển thị của item

        Returns:
            True nếu là low-activity, False nếu không
        """
        return display_name in self.low_activity_symbols

    def track_empty_data(self, display_name, silent_threshold_seconds=0):
        """
        Track empty data warnings

        Args:
            display_name: Tên hiển thị của item
            silent_threshold_seconds: Ngưỡng giây để chuyển sang silent mode (mặc định 0 = silent ngay sau lần đầu)

        Returns:
            Tuple (is_silent, duration_seconds):
                - is_silent: True nếu đang ở silent mode
                - duration_seconds: Số giây đã empty data (None nếu lần đầu)
        """
        current_time = datetime.now()

        if display_name not in self.empty_data_tracking:
            # Lần đầu tiên - chưa silent, sẽ gửi alert
            self.empty_data_tracking[display_name] = {
                "first_time": current_time,
                "count": 1,
                "silent": False,
            }
            return False, None

        tracking = self.empty_data_tracking[display_name]
        tracking["count"] += 1

        duration = (current_time - tracking["first_time"]).total_seconds()

        # Không còn silent mode - luôn gửi alert
        return False, int(duration)

    def reset_empty_data(self, display_name):
        """
        Reset empty data tracking khi có data trở lại

        Args:
            display_name: Tên hiển thị của item

        Returns:
            Số giây đã empty data trước khi reset (None nếu không có tracking)
        """
        if display_name not in self.empty_data_tracking:
            return None

        tracking = self.empty_data_tracking[display_name]
        duration = (datetime.now() - tracking["first_time"]).total_seconds()
        del self.empty_data_tracking[display_name]
        return int(duration)

    def track_stale_data(
        self,
        display_name,
        max_stale_seconds,
        total_stale_seconds,
        data_timestamp,
    ):
        """
        Track stale data và xác định có vượt max_stale không

        Args:
            display_name: Tên hiển thị của item
            max_stale_seconds: Ngưỡng max stale (None = không có giới hạn)
            total_stale_seconds: Tổng số giây data đã stale
            data_timestamp: Timestamp của data hiện tại (ISO format string)

        Returns:
            Tuple (exceeds_max, is_first_time, has_new_data):
                - exceeds_max: True nếu vượt max_stale_seconds
                - is_first_time: True nếu lần đầu vượt (cần gửi final alert)
                - has_new_data: True nếu timestamp thay đổi (có data mới)
        """
        current_time = datetime.now()

        # Track lần đầu stale
        if display_name not in self.first_stale_times:
            self.first_stale_times[display_name] = current_time

        # Check vượt max_stale
        exceeds_max = (
            max_stale_seconds is not None and total_stale_seconds > max_stale_seconds
        )

        # Kiểm tra có data mới không (nếu có data_timestamp)
        has_new_data = False
        if data_timestamp is not None:
            last_seen = self.last_seen_timestamps.get(display_name)
            has_new_data = last_seen is None or data_timestamp != last_seen
            # Cập nhật timestamp đã thấy
            if has_new_data:
                self.last_seen_timestamps[display_name] = data_timestamp

        if exceeds_max:
            if display_name not in self.max_stale_exceeded:
                # Lần đầu vượt - cần gửi final alert
                self.max_stale_exceeded[display_name] = current_time
                return True, True, has_new_data
            else:
                # Đã vượt từ trước - chỉ alert nếu có data mới
                return True, False, has_new_data

        return False, False, has_new_data

    def track_consecutive_stale_days(self, display_name, low_activity_threshold_days=2):
        """
        Track số ngày liên tiếp stale để phát hiện low-activity

        Args:
            display_name: Tên hiển thị của item
            low_activity_threshold_days: Ngưỡng số ngày để xác định low-activity

        Returns:
            Tuple (consecutive_days, became_low_activity):
                - consecutive_days: Số ngày liên tiếp stale
                - became_low_activity: True nếu vừa chuyển sang low-activity
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        last_check = self.consecutive_stale_days.get(display_name)
        if last_check is None:
            self.consecutive_stale_days[display_name] = (current_date, 1)
            return 1, False

        last_date, count = last_check
        if last_date != current_date:
            # Ngày mới
            new_count = count + 1
            self.consecutive_stale_days[display_name] = (current_date, new_count)

            # Check low-activity
            if new_count >= low_activity_threshold_days:
                if display_name not in self.low_activity_symbols:
                    self.low_activity_symbols.add(display_name)
                    return new_count, True

            return new_count, False

        return count, False

    def reset_fresh_data(self, display_name):
        """
        Reset tất cả tracking khi data fresh trở lại

        Args:
            display_name: Tên hiển thị của item
        """
        # Reset các tracking
        if display_name in self.max_stale_exceeded:
            del self.max_stale_exceeded[display_name]

        if display_name in self.last_alert_times:
            del self.last_alert_times[display_name]

        if display_name in self.first_stale_times:
            del self.first_stale_times[display_name]

        if display_name in self.consecutive_stale_days:
            del self.consecutive_stale_days[display_name]

        # Reset empty data nếu có
        if display_name in self.empty_data_tracking:
            del self.empty_data_tracking[display_name]

    def get_stale_count(self):
        """
        Lấy số lượng items đang stale

        Returns:
            Số lượng items stale
        """
        return len(self.first_stale_times)

    def track_alert_count(
        self,
        display_name,
        max_check,
        initial_alert_frequency,
        max_alert_frequency=1800,
    ):
        """
        Track số lần gửi alert để phát hiện ngày lễ

        Khi gửi alert lần thứ max_check+1 trở đi, tăng alert_frequency lên 300 giây
        Cứ mỗi lần gửi alert tiếp tục, tăng thêm 300 giây (tối đa 1800 giây = 30 phút)

        Args:
            display_name: Tên hiển thị của item
            max_check: Ngưỡng số lần gửi alert trước khi kích hoạt holiday logic
            initial_alert_frequency: Alert frequency ban đầu (giây)
            max_alert_frequency: Alert frequency tối đa (mặc định 1800 = 30 phút)

        Returns:
            Tuple (alert_count, current_alert_frequency, exceeded_max_check):
                - alert_count: Số lần gửi alert hiện tại
                - current_alert_frequency: Alert frequency hiện tại (có thể tăng)
                - exceeded_max_check: True nếu vừa vượt quá max_check (lần đầu tiên)
        """
        if display_name not in self.holiday_tracking:
            # Lần đầu tiên ghi nhận alert
            self.holiday_tracking[display_name] = {
                "alert_count": 1,
                "alert_frequency": initial_alert_frequency,
            }
            return 1, initial_alert_frequency, False

        tracking = self.holiday_tracking[display_name]
        tracking["alert_count"] += 1
        alert_count = tracking["alert_count"]

        # Kiểm tra xem vừa vượt quá max_check không
        exceeded = False
        if alert_count == max_check + 1:
            exceeded = True

        # Tính alert_frequency: từ max_check+1 trở đi, tăng 300 giây mỗi lần
        if alert_count > max_check:
            # Số lần tăng = alert_count - max_check
            num_increases = alert_count - max_check
            new_frequency = initial_alert_frequency + (num_increases * 300)
            # Giới hạn tối đa
            current_frequency = min(new_frequency, max_alert_frequency)
        else:
            current_frequency = initial_alert_frequency

        tracking["alert_frequency"] = current_frequency

        return alert_count, current_frequency, exceeded

    def reset_holiday_tracking(self, display_name):
        """
        Reset holiday tracking khi data trở lại bình thường

        Args:
            display_name: Tên hiển thị của item
        """
        if display_name in self.holiday_tracking:
            del self.holiday_tracking[display_name]

    def get_holiday_tracking(self, display_name):
        """
        Lấy thông tin holiday tracking

        Args:
            display_name: Tên hiển thị của item

        Returns:
            Dict với thông tin tracking hoặc None nếu không có
        """
        return self.holiday_tracking.get(display_name)
