import asyncio
from datetime import datetime

from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

from configs.logging_config import LoggerConfig
from configs.database_config import DatabaseConfig
from utils.task_manager_util import TaskManager
from configs.config import DATABASE_CONFIG, PLATFORM_CONFIG
from utils.platform_util import PlatformUtil


class CheckDatabase:
    def __init__(self):
        self.logger_db = LoggerConfig.logger_config("CheckDatabase")
        self.task_manager_db = TaskManager()
        self.config_db = DATABASE_CONFIG
        self.config_platform = PLATFORM_CONFIG
        self.platform_util = PlatformUtil()

        # Tracking alert frequency: {display_name: last_alert_time}
        self.last_alert_times = {}

        # Smart holiday detection
        self.first_stale_times = {}
        self.suspected_holidays = {}

        # Database connector
        self.db_connector = DatabaseConfig()

    async def check_data_database(self, db_name, db_config, symbol=None):
        """Hàm logic check data từ database chạy liên tục"""
        timezone_offset = db_config.get("timezone_offset", 7)
        allow_delay = db_config.get("allow_delay")
        alert_frequency = db_config.get("alert_frequency", 60)
        check_frequency = db_config.get("check_frequency")
        valid_schedule = db_config.get("valid_schedule", {})
        holiday_grace_period = db_config.get("holiday_grace_period", 2 * 3600)

        # Tạo display name
        if symbol:
            display_name = f"{db_name}-{symbol}"
        else:
            display_name = db_name

        while True:
            # Kiểm tra valid_schedule
            if not TimeValidator.is_within_valid_schedule(valid_schedule):
                self.logger_db.info(
                    f"Ngoài lịch kiểm tra cho {display_name}, bỏ qua..."
                )
                await asyncio.sleep(60)
                continue

            # Thực hiện query database
            try:
                latest_time = self.db_connector.query(db_name, db_config, symbol)

                if latest_time is None:
                    raise ValueError("Không có dữ liệu")

                error_message = "Không có dữ liệu mới"
                db_error = False

            except ConnectionError as e:
                error_message = f"Lỗi Database: Không thể kết nối - {str(e)}"
                db_error = True
                self.logger_db.error(f"{error_message} cho {display_name}")
            except ValueError as e:
                error_message = f"Lỗi Database: {str(e)}"
                db_error = True
                self.logger_db.error(f"{error_message} cho {display_name}")
            except Exception as e:
                error_message = f"Lỗi Database: {str(e)}"
                db_error = True
                self.logger_db.error(f"{error_message} cho {display_name}")

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

                # Smart holiday detection
                if display_name not in self.first_stale_times:
                    self.first_stale_times[display_name] = current_time
                    self.logger_db.info(
                        f"Bắt đầu tracking data cũ cho {display_name}, chờ grace period..."
                    )

                first_stale_time = self.first_stale_times[display_name]
                time_since_stale = (current_time - first_stale_time).total_seconds()

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

                # Grace period
                if time_since_stale < holiday_grace_period:
                    grace_remaining = holiday_grace_period - time_since_stale
                    grace_minutes = int(grace_remaining / 60)
                    self.logger_db.info(
                        f"Data cũ cho {display_name}, đang trong grace period. "
                        f"Còn {grace_minutes} phút trước khi gửi alert."
                        f"{' (Nghi ngờ ngày lễ)' if is_suspected_holiday else ''}"
                    )
                    await asyncio.sleep(check_frequency)
                    continue

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
                            f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_dbs} database đang thiếu data). "
                            f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                        )
                    else:
                        context_message = "Dữ liệu database quá hạn"

                    self.platform_util.send_alert_message(
                        api_name=db_name,
                        symbol=symbol,
                        overdue_seconds=overdue_seconds,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="warning" if not is_suspected_holiday else "info",
                        error_message=context_message,
                    )
                    self.last_alert_times[display_name] = current_time
            else:
                self.logger_db.info(f"Dữ liệu database mới cho {display_name}")
                # Reset tracking
                if display_name in self.last_alert_times:
                    del self.last_alert_times[display_name]
                if display_name in self.first_stale_times:
                    del self.first_stale_times[display_name]

            self.logger_db.info(f"Kiểm tra database cho {display_name}")

            # Sleep
            await asyncio.sleep(check_frequency)

    async def run_database_tasks(self):
        """Chạy tất cả các task kiểm tra database"""
        await self.task_manager_db.run_tasks(self.check_data_database, self.config_db)

    def close_connections(self):
        """Đóng tất cả database connections"""
        self.db_connector.close()
