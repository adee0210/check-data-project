import datetime


class ConvertDatetimeUtil:
    """Class cung cấp các phương thức chuyển đổi datetime"""

    @staticmethod
    def convert_isodatetime_todatetime(iso_datetime_str):
        """
        Chuyển đổi ISO datetime string sang datetime object

        Args:
            iso_datetime_str: String ISO format (vd: "2025-12-04T14:30:00Z")

        Returns:
            datetime object hoặc None nếu lỗi
        """
        try:
            return datetime.datetime.fromisoformat(
                iso_datetime_str.replace("Z", "+00:00")
            )
        except ValueError as e:
            print(f"Lỗi convert datetime: {e}")
            return None

    @staticmethod
    def convert_str_to_datetime(datetime_str):
        """
        Chuyển đổi string hoặc datetime object thành datetime object

        Args:
            datetime_str: String hoặc datetime object
                         Hỗ trợ các format:
                         - "2025-12-04 14:30:00" (datetime đầy đủ)
                         - "2025-12-04" (chỉ ngày, giờ mặc định 00:00:00)

        Returns:
            datetime object hoặc None nếu lỗi
        """
        # Nếu đã là datetime object, trả về luôn
        if isinstance(datetime_str, datetime.datetime):
            return datetime_str

        # Nếu là string, parse theo format
        try:
            # Thử parse format đầy đủ "YYYY-MM-DD HH:MM:SS"
            return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Thử parse format chỉ ngày "YYYY-MM-DD"
                return datetime.datetime.strptime(datetime_str, "%Y-%m-%d")
            except ValueError as e:
                print(f"Lỗi convert datetime: {e}")
                print(f"String nhận được: {datetime_str}")
                return None

    @staticmethod
    def convert_utc_to_local(utc_datetime, timezone_offset=7):
        """
        Chuyển đổi datetime từ UTC sang giờ local

        Args:
            utc_datetime: datetime object ở UTC
            timezone_offset: số giờ chênh lệch với UTC (mặc định +7 cho Việt Nam)

        Returns:
            datetime object ở giờ local
        """
        if utc_datetime is None:
            return None

        try:
            # Tạo timezone offset
            offset = datetime.timedelta(hours=timezone_offset)
            local_datetime = utc_datetime + offset
            return local_datetime
        except Exception as e:
            print(f"Lỗi convert UTC to local: {e}")
            return utc_datetime
