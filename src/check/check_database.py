import asyncio
from datetime import datetime

from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

from configs.logging_config import LoggerConfig
from configs.database_config import DatabaseConfig
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util import PlatformUtil
from utils.symbol_resolver_util import SymbolResolverUtil


class CheckDatabase:
    def __init__(self):
        self.logger_db = LoggerConfig.logger_config("CheckDatabase", "database.log")
        self.task_manager_db = TaskManager()
        self.platform_util = PlatformUtil()

        # Tracking alert frequency: {display_name: last_alert_time}
        self.last_alert_times = {}

        # Smart holiday detection
        self.first_stale_times = {}
        self.suspected_holidays = {}

        # Tracking outside schedule status: {display_name: is_outside}
        self.outside_schedule_logged = {}

        # Database connector
        self.db_connector = DatabaseConfig()

    def _load_config(self):
        """Load config from JSON file (called every check cycle)"""
        all_config = LoadConfigUtil.load_json_to_variable("data_sources_config.json")
        # Filter chỉ lấy những config có enable_db_check = true
        return {k: v for k, v in all_config.items() if v.get("enable_db_check", False)}

    async def check_data_database(self, db_name, db_config, symbol=None):
        """Hàm logic check data từ database chạy liên tục"""
        timezone_offset = db_config.get("timezone_offset", 7)
        allow_delay = db_config.get("allow_delay")
        alert_frequency = db_config.get("alert_frequency", 60)
        check_frequency = db_config.get("check_frequency")
        valid_schedule = db_config.get("valid_schedule", {})
        holiday_grace_period = db_config.get("holiday_grace_period", 2 * 3600)
        max_stale_days = db_config.get(
            "max_stale_days", None
        )  # Số ngày tối đa data cũ trước khi dừng alert

        # Tạo display name
        if symbol:
            display_name = f"{db_name}-{symbol}"
        else:
            display_name = db_name

        while True:
            # Kiểm tra valid_schedule
            is_within_schedule = TimeValidator.is_within_valid_schedule(valid_schedule)

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
                    raise ValueError("Không có dữ liệu")

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
                error_message = str(e)
                error_type = "DATABASE"
                db_error = True
                self.logger_db.error(
                    f"Lỗi Database: {error_message} cho {display_name}"
                )
            except Exception as e:
                error_message = str(e)
                error_type = "DATABASE"
                db_error = True
                self.logger_db.error(
                    f"Lỗi Database: {error_message} cho {display_name}"
                )

            if db_error:
                # Xử lý lỗi database - gửi cảnh báo nếu cần
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
                        api_name=db_name,
                        symbol=symbol,
                        overdue_seconds=0,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="error",
                        error_message=error_message,
                        error_type=error_type,
                    )
                    self.last_alert_times[display_name] = current_time

                await asyncio.sleep(check_frequency)
                continue

            # Convert datetime
            dt_latest_time = ConvertDatetimeUtil.convert_str_to_datetime(latest_time)

            # Chuyển đổi timezone nếu cần
            if timezone_offset != 7:
                dt_latest_time = ConvertDatetimeUtil.convert_utc_to_local(
                    dt_latest_time,
                    timezone_offset=7 - timezone_offset,
                )

            # Kiểm tra data fresh
            is_fresh, overdue_seconds = DataValidator.is_data_fresh(
                dt_latest_time, allow_delay
            )

            if not is_fresh:
                time_str = DataValidator.format_time_overdue(
                    overdue_seconds, allow_delay
                )
                self.logger_db.warning(
                    f"CẢNH BÁO: Dữ liệu database quá hạn {time_str} cho {display_name}"
                )

                current_time = datetime.now()
                current_date = current_time.strftime("%Y-%m-%d")

                # Smart holiday detection - track stale databases
                if display_name not in self.first_stale_times:
                    self.first_stale_times[display_name] = current_time

                # Tracking suspected holidays
                if current_date not in self.suspected_holidays:
                    self.suspected_holidays[current_date] = {
                        "db_count": 0,
                        "first_detected": current_time,
                    }

                stale_count = sum(
                    1
                    for name, stale_time in self.first_stale_times.items()
                    if (current_time - stale_time).total_seconds() > allow_delay
                )
                self.suspected_holidays[current_date]["db_count"] = stale_count

                total_dbs = len(self.first_stale_times)
                is_suspected_holiday = stale_count >= max(2, total_dbs * 0.5)

                # Kiểm tra alert frequency
                last_alert = self.last_alert_times.get(display_name)

                should_send_alert = False
                if last_alert is None:
                    # Gửi alert ngay lần đầu tiên khi quá hạn
                    should_send_alert = True
                else:
                    time_since_last_alert = (current_time - last_alert).total_seconds()
                    if time_since_last_alert >= alert_frequency:
                        should_send_alert = True

                # Kiểm tra max_stale_days: Nếu data cũ quá X ngày → dừng gửi alert
                if max_stale_days is not None and should_send_alert:
                    total_stale_seconds = overdue_seconds + allow_delay
                    stale_days = total_stale_seconds / 86400  # Convert to days

                    if stale_days > max_stale_days:
                        # Data đã cũ quá lâu, dừng gửi alert
                        self.logger_db.error(
                            f"LỖI: Data của {display_name} đã cũ {stale_days:.1f} ngày (vượt ngưỡng {max_stale_days} ngày) - "
                            f"Data không ổn định hoặc nguồn dữ liệu đã ngừng cập nhật, cần kiểm tra!"
                        )
                        should_send_alert = False

                if should_send_alert:
                    if is_suspected_holiday:
                        context_message = (
                            f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_dbs} database đang thiếu data). "
                            f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                        )
                        alert_level = "info"
                    else:
                        context_message = "Dữ liệu database quá hạn"
                        alert_level = "warning"

                    self.platform_util.send_alert_message(
                        api_name=db_name,
                        symbol=symbol,
                        overdue_seconds=overdue_seconds,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level=alert_level,
                        error_message=context_message,
                    )
                    self.last_alert_times[display_name] = current_time
                    self.logger_db.info(
                        f"Đã gửi alert cho {display_name}. Alert tiếp theo sau {alert_frequency}s"
                    )
            else:
                # Reset tracking
                if display_name in self.last_alert_times:
                    self.logger_db.info(
                        f"Data của {display_name} đã có dữ liệu mới, reset tracking và sẵn sàng gửi alert nếu lỗi lại"
                    )
                    del self.last_alert_times[display_name]
                if display_name in self.first_stale_times:
                    del self.first_stale_times[display_name]

            self.logger_db.info(
                f"Kiểm tra database {display_name} - {'Có dữ liệu mới' if is_fresh else 'Dữ liệu cũ'}"
            )

            # Sleep
            await asyncio.sleep(check_frequency)

    async def run_database_tasks(self):
        """Chạy tất cả các task kiểm tra database với config được load động"""
        running_tasks = {}  # {display_name: task}

        while True:
            # Reload config để phát hiện thay đổi
            config_db = self._load_config()

            # Cache symbols để tránh gọi resolve 2 lần
            symbols_cache = {}

            # Tạo list các item cần check
            expected_items = set()
            for db_name, db_config in config_db.items():
                # Resolve symbols dựa trên auto_sync_symbols và cache kết quả
                symbols = SymbolResolverUtil.resolve_api_symbols(db_name, db_config)
                symbols_cache[db_name] = symbols

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

            # Start task mới - dùng symbols từ cache
            for db_name, db_config in config_db.items():
                # Lấy symbols từ cache (đã resolve ở trên)
                symbols = symbols_cache[db_name]

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
