import asyncio
from datetime import datetime

from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator
from utils.alert_tracker_util import AlertTracker

from configs.logging_config import LoggerConfig
from configs.database_config.database_manager import DatabaseManager
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util.platform_manager import PlatformManager
from utils.symbol_resolver_util import SymbolResolverUtil


class CheckDatabase:
    """Class kiểm tra data freshness từ database (MongoDB, PostgreSQL)"""

    def __init__(self):
        self.logger_db = LoggerConfig.logger_config("CheckDatabase", "database.log")
        self.task_manager_db = TaskManager()
        self.platform_util = PlatformManager()

        self.db_connector = DatabaseManager()

        # Sử dụng AlertTracker để quản lý tất cả tracking
        self.tracker = AlertTracker()

        # Tracking outside schedule logging
        self.outside_schedule_logged = {}

        # Legacy tracking dictionaries (cần migrate dần sang AlertTracker)
        self.max_stale_exceeded = {}
        self.last_alert_times = {}
        self.first_stale_times = {}
        self.consecutive_stale_days = {}
        self.low_activity_symbols = set()

        # Track timestamp của data cuối cùng để phát hiện data mới
        self.last_seen_timestamps = {}

    def _load_config(self):
        """
        Load config từ JSON file (gọi mỗi chu kỳ check)

        Returns:
            Dict chứa các database config với database.enable = true
        """
        all_config = LoadConfigUtil.load_json_to_variable("data_sources_config.json")
        # Filter chỉ lấy những config có database.enable = true
        return {
            k: v
            for k, v in all_config.items()
            if v.get("database", {}).get("enable", False)
        }

    def _get_active_start_time(self, time_ranges, current_time):
        for time_range in time_ranges:
            start_str, end_str = time_range.split("-")
            start_time = current_time.replace(
                hour=int(start_str[:2]),
                minute=int(start_str[3:5]),
                second=int(start_str[6:]),
            )
            end_time = current_time.replace(
                hour=int(end_str[:2]), minute=int(end_str[3:5]), second=int(end_str[6:])
            )

            if start_time <= current_time <= end_time:
                return start_time

        return None

    async def check_data_database(self, db_name, db_config, symbol=None):
        """
        Hàm logic kiểm tra data từ database chạy liên tục

        Args:
            db_name: Tên database config
            db_config: Dict cấu hình database
            symbol: Optional symbol để filter
        """
        # Tạo display name
        if symbol:
            display_name = f"{db_name}-{symbol}"
        else:
            display_name = db_name

        while True:
            try:
                # Reload config mỗi lần loop để nhận config mới
                # (LoadConfigUtil có cache, chỉ reload khi file thay đổi)
                all_config = self._load_config()
                db_config = all_config.get(db_name, db_config)

                # Đọc config từ cấu trúc mới
                check_cfg = db_config.get("check", {})
                schedule_cfg = db_config.get("schedule", {})

                timezone_offset = check_cfg.get("timezone_offset", 7)
                allow_delay = check_cfg.get("allow_delay", 60)
                alert_frequency = check_cfg.get("alert_frequency", 60)
                check_frequency = check_cfg.get("check_frequency", 10)

                valid_schedule = schedule_cfg

                # Kiểm tra valid_schedule
                is_within_schedule = TimeValidator.is_within_valid_schedule(
                    valid_schedule, timezone_offset
                )

                if not is_within_schedule:
                    # Chỉ log 1 lần khi vào trạng thái ngoài giờ
                    if not self.outside_schedule_logged.get(display_name, False):
                        self.logger_db.info(
                            f"Ngoài lịch kiểm tra cho {display_name}, tạm dừng..."
                        )
                        self.outside_schedule_logged[display_name] = True

                    await asyncio.sleep(60)
                    continue
                else:
                    # Reset flag khi vào lại trong giờ
                    if self.outside_schedule_logged.get(display_name, False):
                        self.logger_db.info(
                            f"Trong lịch kiểm tra cho {display_name}, tiếp tục..."
                        )
                        self.outside_schedule_logged[display_name] = False

                # Thực hiện query database
                try:
                    latest_time = self.db_connector.query(db_name, db_config, symbol)

                    if latest_time is None:
                        raise ValueError("EMPTY_DATA")

                    error_message = "Không có dữ liệu mới"
                    db_error = False

                except ConnectionError as e:
                    error_message = f"Không thể kết nối - {str(e)}"
                    error_type = "DATABASE"
                    db_error = True
                    self.logger_db.error(
                        f"Lỗi Database: {error_message} cho {display_name}"
                    )
                except ValueError as e:
                    error_str = str(e)
                    # Phân biệt EMPTY_DATA vs lỗi khác
                    if "EMPTY_DATA" in error_str:
                        error_message = "Không có dữ liệu trong database"
                        error_type = "DATABASE_WARNING"
                        db_error = True

                        self.logger_db.warning(
                            f"Cảnh báo Database: {error_message} cho {display_name}"
                        )
                if isinstance(latest_time, datetime):
                    dt_latest_time = latest_time
                else:
                    dt_latest_time = ConvertDatetimeUtil.convert_str_to_datetime(
                        latest_time
                    )

                # Chuyển đổi timezone nếu cần
                if timezone_offset != 7:
                    dt_latest_time = ConvertDatetimeUtil.convert_utc_to_local(
                        dt_latest_time, timezone_offset=7 - timezone_offset
                    )

                # Kiểm tra data fresh
                is_fresh, overdue_seconds = DataValidator.is_data_fresh(
                    dt_latest_time, allow_delay
                )

                # Tính adjusted overdue nếu có time_ranges
                schedule_cfg = db_config.get("schedule", {})
                active_start_time = DataValidator.get_active_start_time(
                    schedule_cfg.get("time_ranges") or [] if schedule_cfg else [],
                    datetime.now(),
                )

                if (
                    active_start_time
                    and schedule_cfg
                    and schedule_cfg.get("time_ranges")
                ):
                    overdue_seconds = DataValidator.calculate_adjusted_overdue(
                        dt_latest_time,
                        datetime.now(),
                        schedule_cfg.get("time_ranges", []),
                    )
                    is_fresh = overdue_seconds <= allow_delay

                current_time = datetime.now()
                current_date = current_time.strftime("%Y-%m-%d")

                if is_fresh:
                    self.logger_db.info(
                        f"Kiểm tra database {display_name} - Có dữ liệu mới"
                    )
                    await asyncio.sleep(check_frequency)
                    continue

                time_str = DataValidator.format_time_overdue(
                    overdue_seconds, allow_delay
                )

                if display_name not in self.first_stale_times:
                    self.first_stale_times[display_name] = current_time

                latest_data_date = dt_latest_time.strftime("%Y-%m-%d")
                is_data_from_today = latest_data_date == current_date

                stale_count = self.tracker.get_stale_count()
                total_dbs = max(stale_count, 1)

                # Nội dung cảnh báo đồng bộ giữa log và alert
                warning_message = (
                    f"Dữ liệu database quá hạn {time_str} cho {display_name}"
                )
                self.logger_db.warning(warning_message)

                should_send_alert = self.tracker.should_send_alert(
                    display_name, alert_frequency
                )

                if should_send_alert:
                    db_cfg = db_config.get("database", {})
                    source_info = {"type": "DATABASE"}
                    if "type" in db_cfg:
                        source_info["database_type"] = db_cfg["type"]
                    if "database" in db_cfg:
                        source_info["database"] = db_cfg["database"]
                    if "collection_name" in db_cfg:
                        source_info["collection"] = db_cfg["collection_name"]
                    elif "table_name" in db_cfg:
                        source_info["table"] = db_cfg["table_name"]

                    self.platform_util.send_alert(
                        api_name=db_name,
                        symbol=symbol,
                        overdue_seconds=overdue_seconds,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="warning",
                        error_message=f"Dữ liệu database quá hạn {time_str} cho {display_name}",
                        source_info=source_info,
                    )
                    self.tracker.record_alert_sent(display_name)

                # Sleep
                await asyncio.sleep(check_frequency)

            except Exception as e:
                # Catch-all cho mọi lỗi chưa được handle
                error_message = f"Lỗi không xác định: {str(e)}"
                self.logger_db.error(
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
                    self.platform_util.send_alert(
                        api_name=db_name,
                        symbol=symbol,
                        overdue_seconds=0,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="error",
                        error_message=error_message,
                        error_type="SYSTEM",
                    )
                    self.last_alert_times[display_name] = current_time

                # Sleep trước khi retry
                await asyncio.sleep(check_frequency)

    async def run_database_tasks(self):
        """Chạy tất cả các task kiểm tra database với config được load động"""
        running_tasks = {}  # {display_name: task}

        while True:
            # Reload config để phát hiện thay đổi
            config_db = self._load_config()

            # Tạo list các item cần check
            expected_items = set()
            for db_name, db_config in config_db.items():
                # Resolve symbols mỗi lần để luôn lấy từ database
                symbols = SymbolResolverUtil.resolve_api_symbols(db_name, db_config)

                if symbols is None:
                    # Database không cần symbols
                    expected_items.add(db_name)
                elif isinstance(symbols, list) and len(symbols) > 0:
                    # Có symbols: tạo task cho từng symbol
                    for symbol in symbols:
                        expected_items.add(f"{db_name}-{symbol}")
                else:
                    # Empty list: skip database này
                    continue

            # Phát hiện item mới cần start task
            current_items = set(running_tasks.keys())
            new_items = expected_items - current_items
            removed_items = current_items - expected_items

            # Cancel các task không còn trong config
            for item_name in removed_items:
                if item_name in running_tasks:
                    running_tasks[item_name].cancel()
                    del running_tasks[item_name]
                    self.logger_db.info(f"Đã dừng task cho {item_name}")

                    # Cleanup
                    db_name = item_name.split("-")[0]

            # Start task mới - resolve symbols mỗi lần
            for db_name, db_config in config_db.items():
                # Resolve symbols mỗi lần để luôn lấy từ database
                symbols = SymbolResolverUtil.resolve_api_symbols(db_name, db_config)

                if symbols is None:
                    # Database không cần symbols
                    if db_name in new_items:
                        task = asyncio.create_task(
                            self.check_data_database(db_name, db_config, None)
                        )
                        running_tasks[db_name] = task
                        self.logger_db.info(f"Đã start task mới cho {db_name}")
                elif isinstance(symbols, list) and len(symbols) > 0:
                    # Có symbols: tạo task cho từng symbol
                    for symbol in symbols:
                        display_name = f"{db_name}-{symbol}"
                        if display_name in new_items:
                            task = asyncio.create_task(
                                self.check_data_database(db_name, db_config, symbol)
                            )
                            running_tasks[display_name] = task
                            self.logger_db.info(f"Đã start task mới cho {display_name}")

            # Chờ 10 giây trước khi reload config
            await asyncio.sleep(10)

    def close_connections(self):
        """Đóng tất cả database connections"""
        self.db_connector.close()
