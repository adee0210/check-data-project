import asyncio
from datetime import datetime
import os
from pathlib import Path

from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

from configs.logging_config import LoggerConfig
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util import PlatformUtil


class CheckDisk:
    def __init__(self):
        self.logger_disk = LoggerConfig.logger_config("CheckDisk")
        self.task_manager_disk = TaskManager()
        self.platform_util = PlatformUtil()

        # Tracking alert frequency: {display_name: last_alert_time}
        self.last_alert_times = {}

        # Smart holiday detection
        self.first_stale_times = {}
        self.suspected_holidays = {}

    def _load_config(self):
        """Load config from JSON file (called every check cycle)"""
        return LoadConfigUtil.load_json_to_variable("check_disk_config.json")

    async def check_data_disk(self, disk_name, disk_config, symbol=None):
        """Hàm logic check file/folder trên disk chạy liên tục"""
        file_path = disk_config.get("file_path")  # Đường dẫn file/folder
        check_type = disk_config.get("check_type", "mtime")  # mtime, ctime, atime
        timezone_offset = disk_config.get("timezone_offset", 7)
        allow_delay = disk_config.get("allow_delay")
        alert_frequency = disk_config.get("alert_frequency")
        check_frequency = disk_config.get("check_frequency")
        valid_schedule = disk_config.get("valid_schedule", {})

        if symbol:
            file_path = file_path.format(symbol=symbol)
            display_name = f"{disk_name}-{symbol}"
        else:
            display_name = disk_name

        while True:
            # Kiểm tra valid_schedule
            if not TimeValidator.is_within_valid_schedule(valid_schedule):
                self.logger_disk.info(
                    f"Ngoài lịch kiểm tra cho {display_name}, bỏ qua..."
                )
                await asyncio.sleep(60)
                continue

            try:
                # Kiểm tra file/folder tồn tại
                path = Path(file_path)
                if not path.exists():
                    raise FileNotFoundError(f"Không tìm thấy file/folder: {file_path}")

                # Lấy thời gian modify/create/access
                if check_type == "mtime":
                    timestamp = path.stat().st_mtime
                elif check_type == "ctime":
                    timestamp = path.stat().st_ctime
                elif check_type == "atime":
                    timestamp = path.stat().st_atime
                else:
                    raise ValueError(f"check_type không hợp lệ: {check_type}")

                # Convert timestamp sang datetime
                file_datetime = datetime.fromtimestamp(timestamp)

                error_message = "File/folder không cập nhật"
                disk_error = False

            except FileNotFoundError as e:
                error_message = f"Lỗi Disk: {str(e)}"
                disk_error = True
                self.logger_disk.error(f"{error_message} cho {display_name}")
            except (ValueError, OSError) as e:
                error_message = f"Lỗi Disk: {str(e)}"
                disk_error = True
                self.logger_disk.error(f"{error_message} cho {display_name}")
            except Exception as e:
                error_message = f"Lỗi Disk: {str(e)}"
                disk_error = True
                self.logger_disk.error(f"{error_message} cho {display_name}")

            if disk_error:
                current_time = datetime.now()
                last_alert = self.last_alert_times.get(display_name)

                should_send_alert = False
                if last_alert is None:
                    should_send_alert = True
                else:
                    time_since_last_alert = (current_time - last_alert).total_seconds()
                    if time_since_last_alert >= alert_frequency:
                        should_send_alert = True

                if should_send_alert:
                    self.platform_util.send_alert_message(
                        api_name=disk_name,
                        symbol=symbol,
                        overdue_seconds=0,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="error",
                        error_message=error_message,
                    )
                    self.last_alert_times[display_name] = current_time

                await asyncio.sleep(check_frequency)
                continue

            # Kiểm tra file_datetime fresh
            is_fresh, overdue_seconds = DataValidator.is_data_fresh(
                file_datetime, allow_delay
            )

            if not is_fresh:
                time_str = DataValidator.format_time_overdue(
                    overdue_seconds, allow_delay
                )
                self.logger_disk.warning(
                    f"CẢNH BÁO: File/folder quá hạn {time_str} cho {display_name}"
                )

                current_time = datetime.now()
                current_date = current_time.strftime("%Y-%m-%d")

                # Smart holiday detection
                if display_name not in self.first_stale_times:
                    self.first_stale_times[display_name] = current_time

                # Tracking suspected holidays
                if current_date not in self.suspected_holidays:
                    self.suspected_holidays[current_date] = {
                        "file_count": 0,
                        "first_detected": current_time,
                    }

                stale_count = sum(
                    1
                    for name, stale_time in self.first_stale_times.items()
                    if (current_time - stale_time).total_seconds() > allow_delay
                )
                self.suspected_holidays[current_date]["file_count"] = stale_count

                total_items = len(self.first_stale_times)
                is_suspected_holiday = stale_count >= max(2, total_items * 0.5)

                # Kiểm tra alert frequency
                last_alert = self.last_alert_times.get(display_name)

                should_send_alert = False
                if last_alert is None:
                    should_send_alert = True
                else:
                    time_since_last_alert = (current_time - last_alert).total_seconds()
                    if time_since_last_alert >= alert_frequency:
                        should_send_alert = True

                if should_send_alert:
                    if is_suspected_holiday:
                        context_message = (
                            f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_items} file đang thiếu cập nhật). "
                            f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                        )
                        alert_level = "info"
                    else:
                        context_message = "File/folder không được cập nhật"
                        alert_level = "warning"

                    self.platform_util.send_alert_message(
                        api_name=disk_name,
                        symbol=symbol,
                        overdue_seconds=overdue_seconds,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level=alert_level,
                        error_message=context_message,
                    )
                    self.last_alert_times[display_name] = current_time
                    self.logger_disk.info(
                        f"Đã gửi alert cho {display_name}. Alert tiếp theo sau {alert_frequency}s"
                    )
            else:
                self.logger_disk.info(f"File/folder được cập nhật cho {display_name}")
                # Reset tracking
                if display_name in self.last_alert_times:
                    del self.last_alert_times[display_name]
                if display_name in self.first_stale_times:
                    del self.first_stale_times[display_name]

            self.logger_disk.info(f"Kiểm tra disk cho {display_name} tại {file_path}")

            # Sleep theo check_frequency
            await asyncio.sleep(check_frequency)

    async def run_disk_tasks(self):
        """Chạy tất cả các task kiểm tra disk với config được load động"""
        running_tasks = {}  # {display_name: task}

        while True:
            # Reload config để phát hiện thay đổi
            config_disk = self._load_config()

            # Tạo list các item cần check
            expected_items = set()
            for disk_name, disk_config in config_disk.items():
                symbols = disk_config.get("symbols")
                if symbols:
                    for symbol in symbols:
                        expected_items.add(f"{disk_name}-{symbol}")
                else:
                    expected_items.add(disk_name)

            # Phát hiện item mới cần start task
            current_items = set(running_tasks.keys())
            new_items = expected_items - current_items
            removed_items = current_items - expected_items

            # Cancel các task không còn trong config
            for item_name in removed_items:
                if item_name in running_tasks:
                    running_tasks[item_name].cancel()
                    del running_tasks[item_name]
                    self.logger_disk.info(f"Đã dừng task cho {item_name}")

            # Start task mới
            for disk_name, disk_config in config_disk.items():
                symbols = disk_config.get("symbols")
                if symbols:
                    for symbol in symbols:
                        display_name = f"{disk_name}-{symbol}"
                        if display_name in new_items:
                            task = asyncio.create_task(
                                self.check_data_disk(disk_name, disk_config, symbol)
                            )
                            running_tasks[display_name] = task
                            self.logger_disk.info(
                                f"Đã start task mới cho {display_name}"
                            )
                else:
                    if disk_name in new_items:
                        task = asyncio.create_task(
                            self.check_data_disk(disk_name, disk_config, None)
                        )
                        running_tasks[disk_name] = task
                        self.logger_disk.info(f"Đã start task mới cho {disk_name}")

            # Chờ 10 giây trước khi reload config
            await asyncio.sleep(10)
