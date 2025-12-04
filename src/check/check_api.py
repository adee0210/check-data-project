import asyncio
from datetime import datetime

import requests
from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

from configs.logging_config import LoggerConfig
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util import PlatformUtil
from utils.symbol_resolver_util import SymbolResolverUtil


class CheckAPI:
    def __init__(self):
        self.logger_api = LoggerConfig.logger_config("CheckAPI")
        self.task_manager_api = TaskManager()
        self.platform_util = PlatformUtil()

        # Tracking alert frequency: {display_name: last_alert_time}
        self.last_alert_times = {}

        # Smart holiday detection
        self.first_stale_times = {}
        self.suspected_holidays = {}

        # Tracking outside schedule status: {display_name: is_outside}
        # Để chỉ log 1 lần khi vào/ra khỏi schedule
        self.outside_schedule_logged = {}

    def _load_config(self):
        """Load config from JSON file (called every check cycle)"""
        return LoadConfigUtil.load_json_to_variable("check_api_config.json")

    async def check_data_api(self, api_name, api_config, symbol=None):
        """Hàm logic check data cho API chạy liên tục"""
        uri = api_config.get("uri")
        record_pointer = api_config.get("record_pointer")
        column_to_check = api_config.get("column_to_check")
        timezone_offset = api_config.get("timezone_offset")
        allow_delay = api_config.get("allow_delay")
        alert_frequency = api_config.get("alert_frequency")
        check_frequency = api_config.get("check_frequency")
        valid_schedule = api_config.get("valid_schedule", {})
        holiday_grace_period = api_config.get("holiday_grace_period", 2 * 3600)

        if symbol:
            uri = uri.format(symbol=symbol)
            display_name = f"{api_name}-{symbol}"
        else:
            display_name = api_name

        while True:
            # Kiểm tra valid_schedule: chỉ check trong khoảng thời gian và ngày được phép
            is_within_schedule = TimeValidator.is_within_valid_schedule(valid_schedule)

            if not is_within_schedule:
                # Chỉ log 1 lần khi vào trạng thái ngoài giờ
                if not self.outside_schedule_logged.get(display_name, False):
                    self.logger_api.info(
                        f"Ngoài lịch kiểm tra cho {display_name}, tạm dừng..."
                    )
                    self.outside_schedule_logged[display_name] = True

                await asyncio.sleep(60)
                continue
            else:
                # Reset flag khi vào lại trong giờ
                if self.outside_schedule_logged.get(display_name, False):
                    self.logger_api.info(
                        f"Trong lịch kiểm tra cho {display_name}, tiếp tục..."
                    )
                    self.outside_schedule_logged[display_name] = False

            try:
                r = requests.get(url=uri, timeout=10)
                r.raise_for_status()

                data = r.json()
                record_pointer_data_with_column_to_check = data["data"][record_pointer][
                    column_to_check
                ]

                error_message = "Không có dữ liệu mới"
                api_error = False

            except requests.exceptions.Timeout:
                error_message = "Lỗi API: Timeout khi gọi API"
                api_error = True
                self.logger_api.error(f"{error_message} cho {display_name}")
            except requests.exceptions.ConnectionError:
                error_message = "Lỗi API: Không thể kết nối đến server"
                api_error = True
                self.logger_api.error(f"{error_message} cho {display_name}")
            except requests.exceptions.HTTPError as e:
                error_message = f"Lỗi API: HTTP {e.response.status_code}"
                api_error = True
                self.logger_api.error(f"{error_message} cho {display_name}")
            except (KeyError, IndexError) as e:
                error_message = f"Lỗi API: Dữ liệu không đúng format - {str(e)}"
                api_error = True
                self.logger_api.error(f"{error_message} cho {display_name}")
            except Exception as e:
                error_message = f"Lỗi API: {str(e)}"
                api_error = True
                self.logger_api.error(f"{error_message} cho {display_name}")

            if api_error:
                # Xử lý lỗi API - gửi cảnh báo
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
                        api_name=api_name,
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
                # Luôn ghi log
                self.logger_api.warning(
                    f"CẢNH BÁO: Dữ liệu quá hạn {time_str} cho {display_name}"
                )

                current_time = datetime.now()
                current_date = current_time.strftime("%Y-%m-%d")

                if display_name not in self.first_stale_times:
                    self.first_stale_times[display_name] = current_time
                    self.logger_api.info(
                        f"Bắt đầu tracking data cũ cho {display_name}, chờ grace period..."
                    )

                first_stale_time = self.first_stale_times[display_name]
                time_since_stale = (current_time - first_stale_time).total_seconds()

                if current_date not in self.suspected_holidays:
                    self.suspected_holidays[current_date] = {
                        "api_count": 0,
                        "first_detected": current_time,
                    }

                stale_count = sum(
                    1
                    for name, stale_time in self.first_stale_times.items()
                    if (current_time - stale_time).total_seconds() > allow_delay
                )
                self.suspected_holidays[current_date]["api_count"] = stale_count

                # Nếu nhiều API cùng stale (>= 50% tổng số API) → rất nghi ngờ ngày lễ
                total_apis = len(self.first_stale_times)
                is_suspected_holiday = stale_count >= max(2, total_apis * 0.5)

                # Grace period: Chỉ gửi alert sau khi chờ một khoảng
                if time_since_stale < holiday_grace_period:
                    grace_remaining = holiday_grace_period - time_since_stale
                    grace_minutes = int(grace_remaining / 60)
                    self.logger_api.info(
                        f"Data cũ cho {display_name}, đang trong grace period. "
                        f"Còn {grace_minutes} phút trước khi gửi alert."
                        f"{' (Nghi ngờ ngày lễ)' if is_suspected_holiday else ''}"
                    )
                    await asyncio.sleep(check_frequency)
                    continue

                # Kiểm tra alert_frequency trước khi gửi lên platform
                last_alert = self.last_alert_times.get(display_name)

                should_send_alert = False
                if last_alert is None:
                    # Lần đầu tiên lỗi (sau grace period) → gửi ngay
                    should_send_alert = True
                else:
                    # Kiểm tra đã qua alert_frequency chưa
                    time_since_last_alert = (current_time - last_alert).total_seconds()
                    if time_since_last_alert >= alert_frequency:
                        should_send_alert = True

                if should_send_alert:
                    # Tạo message với ngữ cảnh
                    if is_suspected_holiday:
                        context_message = (
                            f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_apis} API đang thiếu data). "
                            f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                        )
                    else:
                        context_message = "Dữ liệu quá hạn"

                    # Gửi cảnh báo lên platform
                    self.platform_util.send_alert_message(
                        api_name=api_name,
                        symbol=symbol,
                        overdue_seconds=overdue_seconds,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level="warning" if not is_suspected_holiday else "info",
                        error_message=context_message,
                    )
                    # Cập nhật thời gian alert cuối
                    self.last_alert_times[display_name] = current_time
            else:
                self.logger_api.info(f"Đã nhận dữ liệu mới cho {display_name}")
                # Reset alert tracking khi data fresh trở lại
                if display_name in self.last_alert_times:
                    del self.last_alert_times[display_name]
                # Reset stale tracking
                if display_name in self.first_stale_times:
                    del self.first_stale_times[display_name]

            self.logger_api.info(f"Kiểm tra dữ liệu cho {display_name} tại {uri}")

            # Sleep theo check_frequency
            await asyncio.sleep(check_frequency)

    async def run_api_tasks(self):
        """Chạy tất cả các task kiểm tra API với config được load động"""
        running_tasks = {}  # {display_name: task}

        while True:
            # Reload config để phát hiện thay đổi
            config_api = self._load_config()

            # Tạo list các item cần check
            expected_items = set()
            for api_name, api_config in config_api.items():
                # Resolve symbols dựa trên auto_sync_symbols
                symbols = SymbolResolverUtil.resolve_api_symbols(api_name, api_config)

                if symbols is None:
                    # API không cần symbols (ví dụ: gold-data)
                    expected_items.add(api_name)
                elif isinstance(symbols, list) and len(symbols) > 0:
                    # Có symbols: tạo task cho từng symbol
                    for symbol in symbols:
                        expected_items.add(f"{api_name}-{symbol}")
                else:
                    # Empty list: skip API này (đã có warning trong resolver)
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
                    self.logger_api.info(f"Đã dừng task cho {item_name}")

            # Start task mới
            for api_name, api_config in config_api.items():
                # Resolve symbols dựa trên auto_sync_symbols
                symbols = SymbolResolverUtil.resolve_api_symbols(api_name, api_config)

                if symbols is None:
                    # API không cần symbols
                    if api_name in new_items:
                        task = asyncio.create_task(
                            self.check_data_api(api_name, api_config, None)
                        )
                        running_tasks[api_name] = task
                        self.logger_api.info(f"Đã start task mới cho {api_name}")
                elif isinstance(symbols, list) and len(symbols) > 0:
                    # Có symbols: tạo task cho từng symbol
                    for symbol in symbols:
                        display_name = f"{api_name}-{symbol}"
                        if display_name in new_items:
                            task = asyncio.create_task(
                                self.check_data_api(api_name, api_config, symbol)
                            )
                            running_tasks[display_name] = task
                            self.logger_api.info(
                                f"Đã start task mới cho {display_name}"
                            )

            # Chờ 10 giây trước khi reload config
            await asyncio.sleep(10)
