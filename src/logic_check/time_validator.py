from datetime import datetime


class TimeValidator:
    @staticmethod
    def is_within_valid_time(valid_time_config):
        """
        Kiểm tra xem thời gian hiện tại có nằm trong khoảng valid_time không

        Args:
            valid_time_config: Dict chứa các khoảng thời gian hợp lệ
                Ví dụ: {"morning": {"start": "09:00", "end": "11:30"},
                        "afternoon": {"start": "13:00", "end": "14:45"}}

        Returns:
            True nếu trong khoảng thời gian hợp lệ, False nếu không hoặc valid_time rỗng
        """
        if not valid_time_config:
            return True  # Nếu không có cấu hình valid_time thì luôn valid

        current_time = datetime.now().time()

        for period, time_range in valid_time_config.items():
            start_str = time_range.get("start")
            end_str = time_range.get("end")

            if start_str and end_str:
                start_time = datetime.strptime(start_str, "%H:%M").time()
                end_time = datetime.strptime(end_str, "%H:%M").time()

                if start_time <= current_time <= end_time:
                    return True

        return False
