"""
Alert Tracker Utility
Quản lý tất cả tracking cho alert: frequency, stale, low-activity, empty data, etc.
"""

from datetime import datetime
from typing import Dict, Optional, Set, Tuple


class AlertTracker:
    """
    Quản lý tracking cho alert của một checker

    Attributes:
        last_alert_times: Track lần alert cuối cho mỗi item
        first_stale_times: Track lần đầu tiên data bị stale
        suspected_holidays: Track ngày lễ nghi ngờ
        outside_schedule_logged: Track trạng thái outside schedule
        max_stale_exceeded: Track items vượt quá max_stale_seconds
        low_activity_symbols: Set các symbol đã xác định low-activity
        consecutive_stale_days: Track số ngày liên tiếp stale
        empty_data_tracking: Track empty data warnings
        last_holiday_alert_date: Track ngày gửi alert holiday cuối
    """

    def __init__(self):
        self.last_alert_times: Dict[str, datetime] = {}
        self.first_stale_times: Dict[str, datetime] = {}
        self.suspected_holidays: Dict[str, datetime] = {}
        self.outside_schedule_logged: Dict[str, bool] = {}
        self.max_stale_exceeded: Dict[str, datetime] = {}
        self.low_activity_symbols: Set[str] = set()
        self.consecutive_stale_days: Dict[str, Tuple[str, int]] = {}
        self.empty_data_tracking: Dict[str, Dict] = {}
        self.last_holiday_alert_date: Optional[str] = None

        # Track timestamp của data cuối cùng để phát hiện data mới
        self.last_seen_timestamps: Dict[str, str] = {}

    def should_send_alert(self, display_name: str, alert_frequency: int) -> bool:
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

    def record_alert_sent(self, display_name: str) -> None:
        """
        Ghi nhận đã gửi alert

        Args:
            display_name: Tên hiển thị của item
        """
        self.last_alert_times[display_name] = datetime.now()

    def is_in_silent_mode(self, display_name: str) -> bool:
        """
        Kiểm tra xem item có đang ở silent mode không

        Args:
            display_name: Tên hiển thị của item

        Returns:
            True nếu đang ở silent mode, False nếu không
        """
        return display_name in self.max_stale_exceeded

    def is_low_activity(self, display_name: str) -> bool:
        """
        Kiểm tra xem item có phải low-activity không

        Args:
            display_name: Tên hiển thị của item

        Returns:
            True nếu là low-activity, False nếu không
        """
        return display_name in self.low_activity_symbols

    def track_empty_data(
        self, display_name: str, silent_threshold_seconds: int = 0
    ) -> Tuple[bool, Optional[int]]:
        """
        Track empty data warnings và xác định silent mode

        Mặc định (silent_threshold_seconds=0): chỉ gửi alert lần đầu, sau đó silent ngay

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

        # Nếu đã track (count > 1) và chưa silent → chuyển sang silent
        if not tracking["silent"]:
            # Nếu silent_threshold_seconds = 0 → silent ngay sau lần đầu
            # Nếu > 0 → chỉ silent khi vượt ngưỡng thời gian
            if silent_threshold_seconds == 0 or duration > silent_threshold_seconds:
                tracking["silent"] = True
                return True, int(duration)

        return tracking.get("silent", False), int(duration)

    def reset_empty_data(self, display_name: str) -> Optional[int]:
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
        display_name: str,
        max_stale_seconds: Optional[int],
        total_stale_seconds: int,
        data_timestamp: Optional[str] = None,
    ) -> Tuple[bool, bool, bool]:
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

    def track_consecutive_stale_days(
        self, display_name: str, low_activity_threshold_days: int = 2
    ) -> Tuple[int, bool]:
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

    def reset_fresh_data(self, display_name: str) -> None:
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

    def check_holiday_pattern(
        self, current_date: str, is_data_from_today: bool, total_apis: int
    ) -> bool:
        """
        Kiểm tra pattern ngày lễ dựa vào số lượng API stale

        Args:
            current_date: Ngày hiện tại (YYYY-MM-DD)
            is_data_from_today: Data có từ hôm nay không
            total_apis: Tổng số API đang check

        Returns:
            True nếu nghi ngờ là ngày lễ, False nếu không
        """
        stale_count = len(self.first_stale_times)

        is_suspected = (not is_data_from_today) and (
            stale_count >= max(2, int(total_apis * 0.5))
        )

        return is_suspected

    def get_stale_count(self) -> int:
        """
        Lấy số lượng items đang stale

        Returns:
            Số lượng items stale
        """
        return len(self.first_stale_times)
