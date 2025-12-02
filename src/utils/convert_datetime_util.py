import datetime


class ConvertDatetimeUtil:
    @staticmethod
    def convert_isodatetime_todatetime(iso_datetime_str):
        try:
            return datetime.datetime.fromisoformat(
                iso_datetime_str.replace("Z", "+00:00")
            )
        except ValueError as e:
            print(f"Lỗi convert datetime: {e}")
            return None

    @staticmethod
    def convert_str_to_datetime(datetime_str):
        try:
            return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            print(f"Lỗi convert datetime: {e}")
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
