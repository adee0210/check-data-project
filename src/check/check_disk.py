import asyncio
from datetime import datetime
from pathlib import Path
import json
import csv

from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

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

        # Tracking alert frequency: {display_name: last_alert_time}
        self.last_alert_times = {}

        # Smart holiday detection
        self.first_stale_times = {}
        self.suspected_holidays = {}

        # Tracking outside schedule status: {display_name: is_outside}
        self.outside_schedule_logged = {}

        # Track items vượt quá max_stale_days
        self.max_stale_exceeded = {}

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
                raise ValueError("File CSV rỗng")

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
        # Đọc config từ cấu trúc mới
        disk_cfg = disk_config.get("disk", {})
        check_cfg = disk_config.get("check", {})
        schedule_cfg = disk_config.get("schedule", {})

        file_path = disk_cfg.get("file_path")
        file_type = disk_cfg.get("file_type", "mtime")  # json, csv, txt, hoặc mtime
        record_pointer = disk_cfg.get("record_pointer", 0)  # 0 = mới nhất, -1 = cũ nhất
        column_to_check = disk_cfg.get("column_to_check", "datetime")

        timezone_offset = check_cfg.get("timezone_offset", 7)
        allow_delay = check_cfg.get("allow_delay", 60)
        alert_frequency = check_cfg.get("alert_frequency", 60)
        check_frequency = check_cfg.get("check_frequency", 10)
        max_stale_days = check_cfg.get("max_stale_days", None)

        valid_schedule = schedule_cfg

        if symbol:
            file_path = file_path.format(symbol=symbol)
            display_name = f"{disk_name}-{symbol}"
        else:
            display_name = disk_name

        while True:
            try:
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

                    await asyncio.sleep(check_frequency)
                    continue

                # Kiểm tra file_datetime fresh
                is_fresh, overdue_seconds = DataValidator.is_data_fresh(
                    file_datetime, allow_delay
                )

                # EARLY CHECK: Nếu data đã vượt quá max_stale_days, dừng hẳn
                if not is_fresh and max_stale_days is not None:
                    total_stale_seconds = overdue_seconds + allow_delay
                    stale_days = total_stale_seconds / 86400

                    if stale_days > max_stale_days:
                        if display_name not in self.max_stale_exceeded:
                            self.max_stale_exceeded[display_name] = datetime.now()
                            self.logger_disk.warning(
                                f"Data của {display_name} đã cũ {stale_days:.1f} ngày (vượt ngưỡng {max_stale_days} ngày). "
                                f"Dừng check và alert cho item này VĨNH VIỄN."
                            )
                        # Dừng hẳn task này
                        return

                if not is_fresh:
                    time_str = DataValidator.format_time_overdue(
                        overdue_seconds, allow_delay
                    )

                    current_time = datetime.now()
                    current_date = current_time.strftime("%Y-%m-%d")

                    # Track lần đầu data bị cũ
                    if display_name not in self.first_stale_times:
                        self.first_stale_times[display_name] = current_time

                    # Lấy ngày của data mới nhất
                    latest_data_date = file_datetime.strftime("%Y-%m-%d")

                    # Kiểm tra ngày lễ: Data mới nhất có phải hôm nay không?
                    is_data_from_today = latest_data_date == current_date

                    # Đếm số file stale
                    stale_count = sum(
                        1
                        for name in self.first_stale_times.keys()
                        if name in self.first_stale_times
                    )

                    total_files = len(self.first_stale_times)

                    # Chỉ báo ngày lễ khi data KHÔNG phải hôm nay và nhiều file cùng tình trạng
                    is_suspected_holiday = (not is_data_from_today) and (
                        stale_count >= max(2, int(total_files * 0.5))
                    )

                    # Log warning
                    self.logger_disk.warning(
                        f"CẢNH BÁO: File quá hạn {time_str} cho {display_name}"
                        f"{' (Nghi ngờ ngày lễ)' if is_suspected_holiday else ''}"
                    )

                    # Kiểm tra alert_frequency trước khi gửi lên platform
                    last_alert = self.last_alert_times.get(display_name)

                    should_send_alert = False
                    if last_alert is None:
                        should_send_alert = True
                        self.logger_disk.info(
                            f"Lần đầu phát hiện lỗi cho {display_name}, gửi alert ngay"
                        )
                    else:
                        time_since_last_alert = (
                            current_time - last_alert
                        ).total_seconds()
                        if time_since_last_alert >= alert_frequency:
                            should_send_alert = True
                            self.logger_disk.info(
                                f"Đã qua {int(time_since_last_alert)}s kể từ alert cuối cho {display_name}, gửi alert tiếp"
                            )
                        else:
                            remaining = alert_frequency - time_since_last_alert
                            self.logger_disk.debug(
                                f"Chưa đủ alert_frequency cho {display_name}, còn {int(remaining)}s"
                            )

                    if should_send_alert:
                        # Tạo message với ngữ cảnh
                        if is_suspected_holiday:
                            context_message = (
                                f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_files} file đang thiếu data). "
                                f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                            )
                        else:
                            context_message = "File không cập nhật"

                        # Build source_info với file path
                        source_info = {"type": "DISK", "file_path": file_path}

                        # Gửi cảnh báo lên platform
                        self.platform_util.send_alert(
                            api_name=disk_name,
                            symbol=symbol,
                            overdue_seconds=overdue_seconds,
                            allow_delay=allow_delay,
                            check_frequency=check_frequency,
                            alert_frequency=alert_frequency,
                            alert_level=(
                                "warning" if not is_suspected_holiday else "info"
                            ),
                            error_message=context_message,
                            source_info=source_info,
                        )
                        # Cập nhật thời gian alert cuối
                        self.last_alert_times[display_name] = current_time
                else:
                    # Reset alert tracking khi data fresh trở lại
                    if display_name in self.last_alert_times:
                        self.logger_disk.info(
                            f"Data của {display_name} đã có dữ liệu mới, reset tracking và sẵn sàng gửi alert nếu lỗi lại"
                        )
                        del self.last_alert_times[display_name]
                    # Reset stale tracking
                    if display_name in self.first_stale_times:
                        del self.first_stale_times[display_name]

                    self.logger_disk.info(
                        f"Kiểm tra disk {display_name} - Có dữ liệu mới"
                    )

                # Sleep theo check_frequency
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
