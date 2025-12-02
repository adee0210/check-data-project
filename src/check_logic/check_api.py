from datetime import datetime, timedelta
import os
import json
import asyncio

import requests


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

    async def check_data_api(self, api_name, api_config):
        """Hàm logic check data cho API chạy liên tục"""
        uri = api_config.get("uri")
        record_pointer = api_config.get("record_pointer")
        column_to_check = api_config.get("column_to_check")
        allow_delay = api_config.get("allow_delay")
        check_frequency = api_config.get("check_frequency")
        alert_frequency = api_config.get("alert_frequency")
        valid_time = api_config.get("valid_time")
        while True:
            datetime_now = datetime.now()
            r = requests.get(url=uri)
            record_pointer_data_with_column_to_check = r.json()["data"][record_pointer][
                column_to_check
            ]
            dt_record_pointer_data_with_column_to_check = datetime.strptime(
                record_pointer_data_with_column_to_check, "%Y-%m-%d %H:%M:%S"
            )
            if dt_record_pointer_data_with_column_to_check > datetime_now + timedelta(
                seconds=allow_delay
            ):
                self.logger_api.info(
                    f"Da {datetime_now - record_pointer_data_with_column_to_check}s khong co data moi"
                )
            self.logger_api.info(f"Check data cho {api_name} tại {uri}")
            self.logger_api.info(f"Hoàn thành check data cho {api_name}")
            await asyncio.sleep(check_frequency)

    async def run_api_tasks(self):
        await self.task_manager_api.run_tasks(self.check_data_api, self.config_api)
