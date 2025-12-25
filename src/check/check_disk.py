import asyncio
from datetime import datetime
from pathlib import Path
import json
import csv

from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator
from utils.alert_tracker_util import AlertTracker

from configs.logging_config import LoggerConfig
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util.platform_manager import PlatformManager


class CheckDisk:
    """Class kiểm tra freshness của file trên disk bằng cách đọc nội dung hoặc mtime"""

    def __init__(self):
        self.logger_disk = LoggerConfig.logger_config("CheckDisk", "disk.log")
        self.task_manager_disk = TaskManager()
        self.platform_util = PlatformManager()

        # Sử dụng AlertTracker để quản lý tất cả tracking
        self.tracker = AlertTracker()

        # Initialize tracking dictionaries and sets
        self.outside_schedule_logged = {}
        self.last_alert_times = {}
        self.first_stale_times = {}
        self.consecutive_stale_days = {}

    def _load_config(self):
        """
        Load config từ JSON file (gọi mỗi chu kỳ check)

        Returns:
            Dict chứa các disk check config với disk.enable = true
        """
        all_config = LoadConfigUtil.load_json_to_variable("data_sources_config.json")
        # Filter chỉ lấy những config có disk.enable = true
        return {
            k: v
            for k, v in all_config.items()
            if v.get("disk", {}).get("enable", False)
        }

    def _read_datetime_from_file(
        self, file_path: str, file_type: str, record_pointer: int, column_to_check: str
    ) -> datetime:
        """
        Đọc datetime từ file (json, csv, txt)

        Args:
            file_path: Đường dẫn file
            file_type: Loại file ("json", "csv", "txt")
            record_pointer: Vị trí record (0 = mới nhất, -1 = cũ nhất)
            column_to_check: Tên cột chứa datetime

        Returns:
            datetime object

        Raises:
            ValueError: Nếu file type không hỗ trợ hoặc không đọc được datetime
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

        if file_type == "json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list) or len(data) == 0:
                raise ValueError("File JSON rỗng hoặc không phải array")

            record_index = -1 if record_pointer == 0 else 0
            record = data[record_index]

            if column_to_check not in record:
                raise ValueError(
                    f"Không tìm thấy column '{column_to_check}' trong record"
                )

            datetime_str = record[column_to_check]
            return ConvertDatetimeUtil.convert_str_to_datetime(datetime_str)

        elif file_type == "csv":
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if len(rows) == 0:
                raise ValueError("File CSV không có dữ liệu (chỉ có header hoặc rỗng)")

            record_index = -1 if record_pointer == 0 else 0
            record = rows[record_index]

            if column_to_check not in record:
                raise ValueError(f"Không tìm thấy column '{column_to_check}' trong CSV")

            datetime_str = record[column_to_check]
            return ConvertDatetimeUtil.convert_str_to_datetime(datetime_str)

        elif file_type == "txt":
            with open(path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            if len(lines) == 0:
                raise ValueError("File TXT rỗng")

            line_index = -1 if record_pointer == 0 else 0
            datetime_str = lines[line_index]

            return ConvertDatetimeUtil.convert_str_to_datetime(datetime_str)

        else:
            raise ValueError(
                f"File type không hỗ trợ: {file_type}. Chỉ hỗ trợ json, csv, txt"
            )

    async def check_data_disk(self, disk_name, disk_config, symbol=None):
        """
        Hàm logic kiểm tra file trên disk chạy liên tục

        Args:
            disk_name: Tên disk check config
            disk_config: Dict cấu hình disk check
            symbol: Optional symbol cho dynamic path
        """
        # Tạo display name trước
        if symbol:
            display_name = f"{disk_name}-{symbol}"
        else:
            display_name = disk_name

        while True:
            try:
                # Reload config mỗi lần loop để nhận config mới
                # (LoadConfigUtil có cache, chỉ reload khi file thay đổi)
                all_config = self._load_config()
                disk_config = all_config.get(disk_name, disk_config)

                # Đọc config từ cấu trúc mới
                disk_cfg = disk_config.get("disk", {})
                check_cfg = disk_config.get("check", {})
                schedule_cfg = disk_config.get("schedule", {})

                file_path = disk_cfg.get("file_path")
                file_type = disk_cfg.get(
                    "file_type", "mtime"
                )  # json, csv, txt, hoặc mtime
                record_pointer = disk_cfg.get(
                    "record_pointer", 0
                )  # 0 = mới nhất, -1 = cũ nhất
                column_to_check = disk_cfg.get("column_to_check", "datetime")

                timezone_offset = check_cfg.get("timezone_offset", 7)
                allow_delay = check_cfg.get("allow_delay", 60)
                alert_frequency = check_cfg.get("alert_frequency", 60)
                check_frequency = check_cfg.get("check_frequency", 10)
                # Note: max_stale_seconds removed — always use alert_frequency behaviour

                valid_schedule = schedule_cfg

                if symbol:
                    file_path = file_path.format(symbol=symbol)

                # Kiểm tra holidays trước: nếu là ngày lễ thì log riêng và bỏ qua
                holidays = valid_schedule.get("holidays") if valid_schedule else None
                is_holiday = False
                if holidays:
                    current_date = datetime.now().date()
                    for holiday_str in holidays:
                        try:
                            if " " in holiday_str:
                                holiday_date = datetime.strptime(
                                    holiday_str, "%Y-%m-%d %H:%M:%S"
                                ).date()
                            else:
                                holiday_date = datetime.strptime(
                                    holiday_str, "%Y-%m-%d"
                                ).date()

                            if current_date == holiday_date:
                                is_holiday = True
                                break
                        except ValueError:
                            continue

                if is_holiday:
                    # Gửi alert 1 lần duy nhất khi là ngày lễ
                    if not getattr(self.tracker, "holiday_alert_sent", {}).get(
                        display_name, False
                    ):
                        # Gửi alert báo ngày lễ
                        source_info = {"type": "DISK", "file_path": file_path}
                        alert_message = f"Hôm nay là ngày lễ, hệ thống sẽ không gửi alert về dữ liệu quá hạn"

                        self.platform_util.send_alert(
                            api_name=display_name,
                            symbol=symbol,
                            overdue_seconds=0,
                            allow_delay=allow_delay,
                            check_frequency=check_frequency,
                            alert_frequency=alert_frequency,
                            alert_level="info",
                            error_message=alert_message,
                            source_info=source_info,
                        )

                        if not hasattr(self.tracker, "holiday_alert_sent"):
                            self.tracker.holiday_alert_sent = {}
                        self.tracker.holiday_alert_sent[display_name] = True

                        self.logger_disk.info(
                            f"Đã gửi alert thông báo ngày lễ cho {display_name}"
                        )

                    # Vẫn check nhưng không gửi alert stale - tiếp tục xuống dưới

                # Kiểm tra valid_schedule
                is_within_schedule = TimeValidator.is_within_valid_schedule(
                    valid_schedule, timezone_offset
                )

                if not is_within_schedule:
                    if not self.outside_schedule_logged.get(display_name, False):
                        self.logger_disk.info(
                            f"Ngoài lịch kiểm tra cho {display_name}, tạm dừng..."
                        )
                        self.outside_schedule_logged[display_name] = True

                    await asyncio.sleep(60)
                    continue
                else:
                    if self.outside_schedule_logged.get(display_name, False):
                        self.logger_disk.info(
                            f"Trong lịch kiểm tra cho {display_name}, tiếp tục..."
                        )
                        self.outside_schedule_logged[display_name] = False

                # Reset holiday flag chỉ khi không phải ngày lễ
                if not is_holiday and getattr(self, "holiday_logged", {}).get(
                    display_name, False
                ):
                    self.logger_disk.info(
                        f"Không phải ngày lễ, tiếp tục kiểm tra {display_name}"
                    )
                    self.holiday_logged[display_name] = False

                # Inner try block cho file operations
                try:
                    # Kiểm tra file type và lấy datetime
                    if file_type in ["json", "csv", "txt"]:
                        # Đọc datetime từ nội dung file
                        file_datetime = self._read_datetime_from_file(
                            file_path, file_type, record_pointer, column_to_check
                        )

                        # Convert timezone nếu cần
                        if timezone_offset != 7:
                            file_datetime = ConvertDatetimeUtil.convert_utc_to_local(
                                file_datetime, timezone_offset=7 - timezone_offset
                            )

                    elif file_type == "mtime":
                        # Sử dụng file modification time
                        path = Path(file_path)
                        if not path.exists():
                            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

                        timestamp = path.stat().st_mtime
                        file_datetime = datetime.fromtimestamp(timestamp)

                    else:
                        raise ValueError(
                            f"file_type không hợp lệ: {file_type}. "
                            f"Chỉ hỗ trợ: json, csv, txt, mtime"
                        )

                    error_message = "File không cập nhật"
                    disk_error = False

                except FileNotFoundError as e:
                    error_message = str(e)
                    error_type = "DISK"
                    disk_error = True
                    self.logger_disk.error(
                        f"Lỗi Disk: {error_message} cho {display_name}"
                    )
                except (ValueError, KeyError, json.JSONDecodeError) as e:
                    error_message = f"Lỗi đọc file - {str(e)}"
                    error_type = "DISK"
                    disk_error = True
                    self.logger_disk.error(
                        f"Lỗi Disk: {error_message} cho {display_name}"
                    )
                except Exception as e:
                    error_message = str(e)
                    error_type = "DISK"
                    disk_error = True
                    self.logger_disk.error(
                        f"Lỗi Disk: {error_message} cho {display_name}"
                    )

                if disk_error:
                    current_time = datetime.now()
                    last_alert = self.last_alert_times.get(display_name)

                    should_send_alert = False
                    if last_alert is None:
                        should_send_alert = True
                    else:
                        time_since_last_alert = (
                            current_time - last_alert
                        ).total_seconds()
                        if time_since_last_alert >= alert_frequency:
                            should_send_alert = True

                    if should_send_alert:
                        # Build source_info với file path
                        source_info = {"type": "DISK", "file_path": file_path}

                        self.platform_util.send_alert(
                            api_name=disk_name,
                            symbol=symbol,
                            overdue_seconds=0,
                            allow_delay=allow_delay,
                            check_frequency=check_frequency,
                            alert_frequency=alert_frequency,
                            alert_level="error",
                            error_message=error_message,
                            error_type=error_type,
                            source_info=source_info,
                        )
                        self.last_alert_times[display_name] = current_time

                # freshness check
                is_fresh, overdue_seconds = DataValidator.is_data_fresh(
                    file_datetime, allow_delay
                )

                # Tính adjusted overdue nếu có time_ranges
                active_start_time = DataValidator.get_active_start_time(
                    schedule_cfg.get("time_ranges") or [], datetime.now()
                )

                if active_start_time and schedule_cfg.get("time_ranges"):
                    overdue_seconds = DataValidator.calculate_adjusted_overdue(
                        file_datetime,
                        datetime.now(),
                        schedule_cfg.get("time_ranges", []),
                    )
                    is_fresh = overdue_seconds <= allow_delay

                current_time = datetime.now()
                data_timestamp = file_datetime.isoformat()

                if is_fresh:
                    last_seen = self.tracker.last_seen_timestamps.get(display_name)
                    if last_seen is None or last_seen != data_timestamp:
                        self.logger_disk.info(f"Có dữ liệu mới cho {display_name}")
                        self.tracker.last_seen_timestamps[display_name] = data_timestamp

                    # reset state
                    self.tracker.reset_fresh_data(display_name)
                    await asyncio.sleep(check_frequency)
                    continue

                # stale
                time_str = DataValidator.format_time_overdue(
                    overdue_seconds, allow_delay
                )

                self.logger_disk.warning(
                    f"CẢNH BÁO: File quá hạn {time_str} cho {display_name}"
                )

                # Không gửi alert nếu là ngày lễ
                if not is_holiday and self.tracker.should_send_alert(
                    display_name, alert_frequency
                ):
                    source_info = {"type": "DISK", "file_path": file_path}
                    self.platform_util.send_alert(
                        api_name=disk_name,
                        symbol=symbol,
                        overdue_seconds=overdue_seconds,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="warning",
                        error_message="File không cập nhật",
                        source_info=source_info,
                    )
                    self.tracker.record_alert_sent(display_name)

                await asyncio.sleep(check_frequency)

            except Exception as e:
                # Catch-all cho bất kỳ lỗi nào chưa được xử lý
                error_message = f"Lỗi không xác định: {str(e)}"
                self.logger_disk.error(
                    f"CRITICAL ERROR trong task {display_name}: {error_message}",
                    exc_info=True,
                )

                # Gửi alert về lỗi critical
                current_time = datetime.now()
                last_alert = self.last_alert_times.get(display_name)

                should_send_alert = (
                    last_alert is None
                    or (current_time - last_alert).total_seconds() >= alert_frequency
                )

                if should_send_alert:
                    # Build source_info với file path
                    source_info = {"type": "DISK", "file_path": file_path}

                    self.platform_util.send_alert(
                        api_name=disk_name,
                        symbol=symbol,
                        overdue_seconds=0,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="error",
                        error_message=error_message,
                        error_type="SYSTEM",
                        source_info=source_info,
                    )
                    self.last_alert_times[display_name] = current_time

                # Sleep trước khi retry
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
                # Kiểm tra xem có symbols không (giống API logic)
                symbols_cfg = disk_config.get("symbols", {})
                if symbols_cfg.get("auto_sync"):
                    # TODO: Implement symbol resolution nếu cần
                    # Hiện tại bỏ qua auto_sync cho disk
                    pass

                symbols_list = symbols_cfg.get("list", [])
                if symbols_list and len(symbols_list) > 0:
                    for symbol in symbols_list:
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
                symbols_cfg = disk_config.get("symbols", {})
                symbols_list = symbols_cfg.get("list", [])

                if symbols_list and len(symbols_list) > 0:
                    for symbol in symbols_list:
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
