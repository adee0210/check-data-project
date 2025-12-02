import asyncio
from datetime import datetime

import requests
from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

from configs.logging_config import LoggerConfig
from utils.task_manager_util import TaskManager
from configs.config import API_CONFIG, PLATFORM_CONFIG

# from utils.platform_util import PlatformUtil


class CheckAPI:
    def __init__(self):
        self.logger_api = LoggerConfig.logger_config("CheckAPI")
        self.task_manager_api = TaskManager()
        self.config_api = API_CONFIG
        self.config_platform = PLATFORM_CONFIG

        # self.platform_util = PlatformUtil()

    async def check_data_api(self, api_name, api_config, symbol=None):
        """Hàm logic check data cho API chạy liên tục"""
        uri = api_config.get("uri")
        record_pointer = api_config.get("record_pointer")
        column_to_check = api_config.get("column_to_check")
        timezone_offset = api_config.get("timezone_offset", 7)  # Mặc định GMT+7
        allow_delay = api_config.get("allow_delay")
        check_frequency = api_config.get("check_frequency")
        valid_time = api_config.get("valid_time", {})

        # Thay thế {symbol} trong URI nếu có
        if symbol:
            uri = uri.format(symbol=symbol)
            display_name = f"{api_name}-{symbol}"
        else:
            display_name = api_name

        while True:
            # Kiểm tra valid_time: chỉ check trong khoảng thời gian cho phép
            if not TimeValidator.is_within_valid_time(valid_time):
                self.logger_api.info(
                    f"Ngoài thời gian kiểm tra cho {display_name}, bỏ qua..."
                )
                await asyncio.sleep(60)  # Chờ 1 phút rồi kiểm tra lại
                continue

            # Thực hiện kiểm tra dữ liệu
            r = requests.get(url=uri)
            record_pointer_data_with_column_to_check = r.json()["data"][record_pointer][
                column_to_check
            ]

            dt_record_pointer_data_with_column_to_check = (
                ConvertDatetimeUtil.convert_str_to_datetime(
                    record_pointer_data_with_column_to_check
                )
            )

            # Chuyển đổi từ múi giờ của data sang giờ local (GMT+7)
            if timezone_offset != 7:  # Chỉ convert nếu không phải GMT+7
                dt_record_pointer_data_with_column_to_check = (
                    ConvertDatetimeUtil.convert_utc_to_local(
                        dt_record_pointer_data_with_column_to_check,
                        timezone_offset=7 - timezone_offset,
                    )
                )

            # Sử dụng DataValidator để kiểm tra dữ liệu
            is_fresh, overdue_seconds = DataValidator.is_data_fresh(
                dt_record_pointer_data_with_column_to_check, allow_delay
            )

            if not is_fresh:
                time_str = DataValidator.format_time_overdue(
                    overdue_seconds, allow_delay
                )
                self.logger_api.warning(
                    f"CẢNH BÁO: Dữ liệu quá hạn {time_str} cho {display_name}"
                )
            else:
                self.logger_api.info(f"Đã nhận dữ liệu mới cho {display_name}")

            self.logger_api.info(f"Kiểm tra dữ liệu cho {display_name} tại {uri}")

            # Sleep theo check_frequency
            await asyncio.sleep(check_frequency)

    async def run_api_tasks(self):
        await self.task_manager_api.run_tasks(self.check_data_api, self.config_api)
