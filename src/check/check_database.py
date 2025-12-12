import asyncio
from datetime import datetime

from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

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

        self.last_alert_times = {}

        self.first_stale_times = {}
        self.suspected_holidays = {}

        self.outside_schedule_logged = {}

        self.db_connector = DatabaseManager()

        # Symbols cache ở class level để persist qua các reload
        self.symbols_cache = {}

        # Track items vượt quá max_stale_seconds (đã gửi alert "dừng gửi thông báo")
        self.max_stale_exceeded = {}  # {display_name: datetime}

        # Track low-activity symbols (đã xác nhận giao dịch thấp - không gửi alert nữa)
        self.low_activity_symbols = set()  # {display_name, ...}

        # Track consecutive days without data (để phát hiện low-activity)
        self.consecutive_stale_days = {}  # {display_name: (last_check_date, count)}

        # Track last holiday alert date
        self.last_holiday_alert_date = None  # Last date khi gửi alert "ngày lễ"

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
                max_stale_seconds = check_cfg.get("max_stale_seconds", None)

                valid_schedule = schedule_cfg
                holiday_grace_period = check_cfg.get("holiday_grace_period", 2 * 3600)

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
                        time_since_last_alert = (
                            current_time - last_alert
                        ).total_seconds()
                        if time_since_last_alert >= alert_frequency:
                            should_send_alert = True

                    if should_send_alert:
                        # Build source_info với database connection details
                        db_cfg = db_config.get("database", {})
                        source_info = {"type": "DATABASE"}

                        if "type" in db_cfg:
                            source_info["database_type"] = db_cfg[
                                "type"
                            ]  # mongodb hoặc postgresql

                        if "database" in db_cfg:
                            source_info["database"] = db_cfg["database"]

                        if "collection_name" in db_cfg:
                            source_info["collection"] = db_cfg["collection_name"]
                        elif "table_name" in db_cfg:
                            source_info["table"] = db_cfg["table_name"]

                        self.platform_util.send_alert(
                            api_name=db_name,
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

                # Convert datetime
                dt_latest_time = ConvertDatetimeUtil.convert_str_to_datetime(
                    latest_time
                )

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

                current_time = datetime.now()
                current_date = current_time.strftime("%Y-%m-%d")

                # ===== EARLY CHECK: Low-activity symbol - chỉ log, không gửi alert =====
                if display_name in self.low_activity_symbols:
                    if is_fresh:
                        self.logger_db.info(
                            f"[LOW-ACTIVITY] {display_name} có data mới nhưng vẫn được đánh dấu low-activity, không gửi alert"
                        )
                    else:
                        self.logger_db.debug(
                            f"[LOW-ACTIVITY] {display_name} không có data mới, skip alert"
                        )
                    await asyncio.sleep(check_frequency)
                    continue

                # ===== CASE 1: Data FRESH - Reset tất cả tracking =====
                if is_fresh:
                    if display_name in self.max_stale_exceeded:
                        self.logger_db.info(
                            f"{display_name} có data mới, reset max_stale_exceeded tracking"
                        )
                        del self.max_stale_exceeded[display_name]

                    if display_name in self.last_alert_times:
                        del self.last_alert_times[display_name]

                    if display_name in self.first_stale_times:
                        del self.first_stale_times[display_name]

                    if display_name in self.consecutive_stale_days:
                        self.logger_db.info(
                            f"{display_name} có data mới, reset consecutive_stale_days"
                        )
                        del self.consecutive_stale_days[display_name]

                    self.logger_db.info(
                        f"Kiểm tra database {display_name} - Có dữ liệu mới"
                    )
                    await asyncio.sleep(check_frequency)
                    continue

                # ===== CASE 2: Data STALE - Xử lý phức tạp =====
                time_str = DataValidator.format_time_overdue(
                    overdue_seconds, allow_delay
                )

                if display_name not in self.first_stale_times:
                    self.first_stale_times[display_name] = current_time

                latest_data_date = dt_latest_time.strftime("%Y-%m-%d")
                is_data_from_today = latest_data_date == current_date

                total_stale_seconds = overdue_seconds + allow_delay
                exceeds_max_stale = (
                    max_stale_seconds is not None
                    and total_stale_seconds > max_stale_seconds
                )

                # ===== CASE 2A: Vượt max_stale_seconds =====
                if exceeds_max_stale:
                    if display_name not in self.max_stale_exceeded:
                        self.max_stale_exceeded[display_name] = current_time

                        hours = int(total_stale_seconds // 3600)
                        minutes = int((total_stale_seconds % 3600) // 60)
                        seconds = int(total_stale_seconds % 60)

                        max_hours = int(max_stale_seconds // 3600)
                        max_minutes = int((max_stale_seconds % 3600) // 60)
                        max_seconds = int(max_stale_seconds % 60)

                        self.logger_db.warning(
                            f"Data của {display_name} đã cũ {hours} giờ {minutes} phút {seconds} giây "
                            f"(vượt ngưỡng {max_hours} giờ {max_minutes} phút {max_seconds} giây). "
                            f"Gửi alert cuối cùng, sau đó chỉ log."
                        )

                        status_message = f"Data quá cũ (vượt {max_hours} giờ {max_minutes} phút {max_seconds} giây), không có data mới, dừng gửi thông báo"

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
                            error_message="Không có dữ liệu mới",
                            source_info=source_info,
                            status_message=status_message,
                        )
                        self.last_alert_times[display_name] = current_time
                    else:
                        self.logger_db.info(
                            f"[SILENT MODE] {display_name} vẫn không có data, chỉ log (không gửi alert)"
                        )

                    # Track consecutive stale days
                    last_check = self.consecutive_stale_days.get(display_name)
                    if last_check is None:
                        self.consecutive_stale_days[display_name] = (current_date, 1)
                    else:
                        last_date, count = last_check
                        if last_date != current_date:
                            new_count = count + 1
                            self.consecutive_stale_days[display_name] = (
                                current_date,
                                new_count,
                            )

                            if new_count >= 2:
                                self.low_activity_symbols.add(display_name)
                                self.logger_db.warning(
                                    f"[LOW-ACTIVITY DETECTED] {display_name} đã {new_count} ngày liên tiếp không có data. "
                                    f"Đánh dấu là giao dịch thấp, dừng gửi alert vĩnh viễn."
                                )

                # ===== CASE 2B: Chưa vượt max_stale - Alert bình thường =====
                else:
                    stale_count = len(self.first_stale_times)
                    total_dbs = max(stale_count, 1)

                    is_suspected_holiday = (not is_data_from_today) and (
                        stale_count >= max(2, int(total_dbs * 0.5))
                    )

                    self.logger_db.warning(
                        f"CẢNH BÁO: Dữ liệu database quá hạn {time_str} cho {display_name}"
                        f"{' (Nghi ngờ ngày lễ)' if is_suspected_holiday else ''}"
                    )

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
                        if is_suspected_holiday:
                            if self.last_holiday_alert_date != current_date:
                                context_message = (
                                    f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_dbs} database đang thiếu data). "
                                    f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                                )

                                db_cfg = db_config.get("database", {})
                                source_info = {"type": "DATABASE"}
                                if "type" in db_cfg:
                                    source_info["database_type"] = db_cfg["type"]
                                if "database" in db_cfg:
                                    source_info["database"] = db_cfg["database"]
                                if "collection_name" in db_cfg:
                                    source_info["collection"] = db_cfg[
                                        "collection_name"
                                    ]
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
                                    error_message=context_message,
                                    source_info=source_info,
                                )
                                self.last_alert_times[display_name] = current_time
                                self.last_holiday_alert_date = current_date
                                self.logger_db.info(
                                    f"Đã gửi alert ngày lễ cho {display_name}"
                                )
                            else:
                                self.logger_db.info(
                                    f"Đã gửi alert ngày lễ hôm nay, skip để tránh spam"
                                )
                        else:
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
                                error_message="Không có dữ liệu mới",
                                source_info=source_info,
                            )
                            self.last_alert_times[display_name] = current_time

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
                # Chỉ resolve symbols khi chưa có trong cache
                if db_name not in self.symbols_cache:
                    symbols = SymbolResolverUtil.resolve_api_symbols(db_name, db_config)
                    self.symbols_cache[db_name] = symbols
                else:
                    symbols = self.symbols_cache[db_name]

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

                    # Cleanup symbols cache
                    db_name = item_name.split("-")[0]
                    if db_name not in config_db and db_name in self.symbols_cache:
                        del self.symbols_cache[db_name]
                        self.logger_db.info(f"Đã xóa symbols cache cho {db_name}")

            # Start task mới - dùng symbols từ class cache
            for db_name, db_config in config_db.items():
                # Lấy symbols từ class cache (đã resolve ở trên)
                symbols = self.symbols_cache.get(db_name)

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
