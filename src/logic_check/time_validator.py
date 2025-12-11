from datetime import datetime, timezone, timedelta


class TimeValidator:
    """Xử lý logic kiểm tra thời gian nằm trong lịch hợp lệ"""

    @staticmethod
    def _check_single_schedule(schedule, current_weekday, current_time):
        """
        Kiểm tra một lịch trình đơn

        Args:
            schedule: Dict với format {"valid_days": [...], "time_ranges": "..."} hoặc {"days": [...], "hours": "..."} (backward compatibility)
            current_weekday: Ngày hiện tại (0-6)
            current_time: Thời gian hiện tại

        Returns:
            True nếu hợp lệ, False nếu không
        """
        # Support both new and old key names
        days = (
            schedule.get("valid_days")
            if "valid_days" in schedule
            else schedule.get("days")
        )
        hours = (
            schedule.get("time_ranges")
            if "time_ranges" in schedule
            else schedule.get("hours")
        )

        # Kiểm tra ngày: None = mọi ngày, [] = mọi ngày, [0,1,2...] = các ngày cụ thể
        if days is not None and len(days) > 0:
            if current_weekday not in days:
                return False

        # Kiểm tra giờ: None = 24h, "HH:MM-HH:MM" = khoảng thời gian, ["...", "..."] = nhiều khoảng
        if hours is None:
            return True  # Không giới hạn giờ

        # Nếu hours là list, kiểm tra từng khoảng
        if isinstance(hours, list):
            for hour_range in hours:
                if TimeValidator._check_time_range(hour_range, current_time):
                    return True
            return False

        # Nếu hours là string, kiểm tra khoảng đó
        return TimeValidator._check_time_range(hours, current_time)

    @staticmethod
    def _check_time_range(hour_range, current_time):
        """
        Kiểm tra xem thời gian hiện tại có nằm trong khoảng không

        Args:
            hour_range: String format "HH:MM-HH:MM"
            current_time: Thời gian hiện tại

        Returns:
            True nếu trong khoảng, False nếu không
        """
        if not hour_range or "-" not in hour_range:
            return True

        try:
            start_str, end_str = hour_range.split("-")
            start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
            end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
            return start_time <= current_time <= end_time
        except (ValueError, AttributeError):
            return True  # Nếu format sai, cho phép

    @staticmethod
    def is_within_valid_schedule(valid_schedule, timezone_offset=7):
        """
        Kiểm tra xem thời điểm hiện tại có nằm trong lịch hợp lệ không

        NOTE: Schedule trong config LUÔN theo giờ VN (UTC+7)
        timezone_offset chỉ để convert thời gian hiện tại sang UTC+7 để so sánh

        Args:
            valid_schedule: Có thể là:
                1. None - Không giới hạn (24/7)
                2. Dict đơn giản:
                   {"valid_days": [0,1,2,3,4], "time_ranges": "08:00-17:00"}
                   {"valid_days": [0,1,2,3,4], "time_ranges": ["08:00-11:30", "13:00-16:00"]}
                   {"valid_days": None, "time_ranges": None}  # 24/7
                3. List nhiều schedules:
                   [
                       {"valid_days": [0,1,2,3,4], "time_ranges": None},
                       {"valid_days": [5,6], "time_ranges": "09:00-17:00"}
                   ]
                4. Dict cũ (backward compatible):
                   {"period_name": {"days": [...], "start": "...", "end": "..."}}
            timezone_offset: KHÔNG DÙNG - để backward compatibility. Schedule luôn theo UTC+7

        Returns:
            True nếu trong khoảng thời gian hợp lệ, False nếu không
        """
        if valid_schedule is None:
            return True  # None = không giới hạn

        if not valid_schedule:
            return True  # {} hoặc [] = không giới hạn

        # Get current time in Vietnam timezone (UTC+7) - schedule luôn theo giờ VN
        tz = timezone(timedelta(hours=7))
        now = datetime.now(tz)
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        current_time = now.time()

        # Trường hợp 1: List của nhiều schedules
        if isinstance(valid_schedule, list):
            for schedule in valid_schedule:
                if TimeValidator._check_single_schedule(
                    schedule, current_weekday, current_time
                ):
                    return True
            return False

        # Trường hợp 2: Dict với format mới {"valid_days": ..., "time_ranges": ...}
        if "valid_days" in valid_schedule or "time_ranges" in valid_schedule:
            return TimeValidator._check_single_schedule(
                valid_schedule, current_weekday, current_time
            )

        # Trường hợp 3: Dict với format cũ {"days": ..., "hours": ...} (backward compatibility)
        if "days" in valid_schedule or "hours" in valid_schedule:
            return TimeValidator._check_single_schedule(
                valid_schedule, current_weekday, current_time
            )

        # Trường hợp 4: Dict với format cũ hơn (backward compatible)
        # {"period_name": {"days": [...], "start": "...", "end": "..."}}
        for period, schedule in valid_schedule.items():
            # Skip nếu schedule không phải dict
            if not isinstance(schedule, dict):
                continue

            days = schedule.get("days", [])
            start_str = schedule.get("start")
            end_str = schedule.get("end")

            # Kiểm tra ngày
            day_valid = not days or current_weekday in days

            # Kiểm tra giờ
            time_valid = True
            if start_str and end_str:
                try:
                    start_time = datetime.strptime(start_str, "%H:%M").time()
                    end_time = datetime.strptime(end_str, "%H:%M").time()
                    time_valid = start_time <= current_time <= end_time
                except ValueError:
                    time_valid = True

            # Nếu cả ngày và giờ đều hợp lệ thì return True
            if day_valid and time_valid:
                return True

        return False
