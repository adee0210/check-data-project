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
