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
        Chuyển đổi string, date, hoặc datetime object thành datetime object

        Hỗ trợ:
        - datetime.datetime object (trả về luôn)
        - datetime.date object (convert sang datetime với time 00:00:00)
        - String ISO format: "2025-12-04T14:30:00", "2025-12-04T14:30:00Z"
        - String datetime: "2025-12-04 14:30:00"
        - String date: "2025-12-04"
        - Unix timestamp (int/float)

        Args:
            datetime_str: String, date, datetime object, hoặc timestamp

        Returns:
            datetime object hoặc raise ValueError nếu không parse được
        """
        # Nếu là None, raise error
        if datetime_str is None:
            raise ValueError("datetime_str không được None")

        # Nếu đã là datetime object, trả về luôn
        if isinstance(datetime_str, datetime.datetime):
            return datetime_str

        # Nếu là datetime.date (PostgreSQL thường trả về kiểu này)
        if isinstance(datetime_str, datetime.date):
            # Convert date sang datetime với time 00:00:00
            return datetime.datetime.combine(datetime_str, datetime.time.min)

        # Nếu là số (timestamp)
        if isinstance(datetime_str, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(datetime_str)
            except (ValueError, OSError) as e:
                raise ValueError(f"Không thể convert timestamp {datetime_str}: {e}")

        # Nếu là string, thử parse theo nhiều format
        if isinstance(datetime_str, str):
            # Loại bỏ whitespace
            datetime_str = datetime_str.strip()

            # Thử ISO format với Z
            if "T" in datetime_str:
                try:
                    return datetime.datetime.fromisoformat(
                        datetime_str.replace("Z", "+00:00").replace("z", "+00:00")
                    )
                except ValueError:
                    pass

            # Thử format đầy đủ "YYYY-MM-DD HH:MM:SS"
            try:
                return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

            # Thử format với microseconds "YYYY-MM-DD HH:MM:SS.ffffff"
            try:
                return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                pass

            # Thử format chỉ ngày "YYYY-MM-DD"
            try:
                return datetime.datetime.strptime(datetime_str, "%Y-%m-%d")
            except ValueError:
                pass

            # Thử format DD/MM/YYYY
            try:
                return datetime.datetime.strptime(datetime_str, "%d/%m/%Y")
            except ValueError:
                pass

            # Thử format DD/MM/YYYY HH:MM:SS
            try:
                return datetime.datetime.strptime(datetime_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                pass

        # Nếu không parse được, raise error với thông tin chi tiết
        raise ValueError(
            f"Không thể convert thành datetime. "
            f"Type: {type(datetime_str)}, Value: {datetime_str}"
        )

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
