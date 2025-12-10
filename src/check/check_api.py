"""Module kiểm tra API endpoints"""

import asyncio
from datetime import datetime

import requests
from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator

from configs.logging_config import LoggerConfig
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util import PlatformManager
from utils.symbol_resolver_util import SymbolResolverUtil


class CheckAPI:
    """Class kiểm tra data freshness từ API endpoints"""

    def __init__(self):
        self.logger_api = LoggerConfig.logger_config("CheckAPI", "api.log")
        self.task_manager_api = TaskManager()
        self.platform_util = PlatformManager()

        # Tracking alert frequency: {display_name: last_alert_time}
        self.last_alert_times = {}

        # Smart holiday detection
        self.first_stale_times = {}
        self.suspected_holidays = {}

        # Tracking outside schedule status: {display_name: is_outside}
        # Để chỉ log 1 lần khi vào/ra khỏi schedule
        self.outside_schedule_logged = {}

        # Symbols cache ở class level để persist qua các reload
        # Format: {api_name: symbols_list}
        self.symbols_cache = {}

        # Track items vượt quá max_stale_days
        self.max_stale_exceeded = {}

    def _load_config(self):
        """
        Load config từ JSON file (gọi mỗi chu kỳ check)

        Returns:
            Dict chứa các API config với api.enable = true
        """
        all_config = LoadConfigUtil.load_json_to_variable("data_sources_config.json")
        # Filter chỉ lấy những config có api.enable = true
        return {
            k: v for k, v in all_config.items() if v.get("api", {}).get("enable", False)
        }

    async def check_data_api(self, api_name, api_config, symbol=None):
        """
        Hàm logic kiểm tra data từ API chạy liên tục

        Args:
            api_name: Tên API config
            api_config: Dict cấu hình API
            symbol: Optional symbol để filter
        """
        # Đọc config từ cấu trúc mới
        api_cfg = api_config.get("api", {})
        check_cfg = api_config.get("check", {})
        schedule_cfg = api_config.get("schedule", {})
        symbols_cfg = api_config.get("symbols", {})

        uri = api_cfg.get("url")
        record_pointer = api_cfg.get("record_pointer", 0)
        column_to_check = api_cfg.get("column_to_check", "datetime")

        timezone_offset = check_cfg.get("timezone_offset", 7)
        allow_delay = check_cfg.get("allow_delay", 60)
        alert_frequency = check_cfg.get("alert_frequency", 60)
        check_frequency = check_cfg.get("check_frequency", 10)
        max_stale_days = check_cfg.get("max_stale_days", None)

        valid_schedule = schedule_cfg
        holiday_grace_period = check_cfg.get("holiday_grace_period", 2 * 3600)

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

                # Kiểm tra cấu trúc dữ liệu
                if "data" not in data:
                    raise KeyError("Response không có key 'data'")

                if not isinstance(data["data"], list) or len(data["data"]) == 0:
                    raise IndexError("Mảng 'data' rỗng hoặc không phải list")

                if record_pointer >= len(data["data"]):
                    raise IndexError(
                        f"record_pointer {record_pointer} vượt quá độ dài mảng {len(data['data'])}"
                    )

                record_pointer_data_with_column_to_check = data["data"][record_pointer][
                    column_to_check
                ]

                error_message = "Không có dữ liệu mới"
                api_error = False

            except requests.exceptions.Timeout:
                error_message = "Timeout khi gọi API"
                error_type = "API"
                api_error = True
                self.logger_api.error(f"Lỗi API: {error_message} cho {display_name}")
            except requests.exceptions.ConnectionError:
                error_message = "Không thể kết nối đến server"
                error_type = "API"
                api_error = True
                self.logger_api.error(f"Lỗi API: {error_message} cho {display_name}")
            except requests.exceptions.HTTPError as e:
                error_message = f"HTTP {e.response.status_code}"
                error_type = "API"
                api_error = True
                self.logger_api.error(f"Lỗi API: {error_message} cho {display_name}")
            except (KeyError, IndexError) as e:
                error_message = f"Dữ liệu không đúng format - {str(e)}"
                error_type = "API"
                api_error = True
                self.logger_api.error(f"Lỗi API: {error_message} cho {display_name}")
            except Exception as e:
                error_message = str(e)
                error_type = "API"
                api_error = True
                self.logger_api.error(f"Lỗi API: {error_message} cho {display_name}")

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
                        error_type=error_type,
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

            # EARLY CHECK: Nếu data đã vượt quá max_stale_days, dừng hẳn
            if not is_fresh and max_stale_days is not None:
                total_stale_seconds = overdue_seconds + allow_delay
                stale_days = total_stale_seconds / 86400

                if stale_days > max_stale_days:
                    # Chỉ log warning 1 lần rồi dừng hẳn
                    if display_name not in self.max_stale_exceeded:
                        self.max_stale_exceeded[display_name] = datetime.now()
                        self.logger_api.warning(
                            f"Data của {display_name} đã cũ {stale_days:.1f} ngày (vượt ngưỡng {max_stale_days} ngày). "
                            f"Dừng check và alert cho item này VĨNH VIỄN."
                        )

                    # Dừng hẳn task này
                    return

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

                # Lấy ngày của data mới nhất
                latest_data_date = dt_record_pointer_data_with_column_to_check.strftime(
                    "%Y-%m-%d"
                )

                # Kiểm tra ngày lễ: Data mới nhất có phải hôm nay không?
                is_data_from_today = latest_data_date == current_date

                # Đếm số API stale
                stale_count = sum(
                    1
                    for name in self.first_stale_times.keys()
                    if name in self.first_stale_times
                )

                total_apis = len(self.first_stale_times)

                # Chỉ báo ngày lễ khi data KHÔNG phải hôm nay và nhiều API cùng tình trạng
                is_suspected_holiday = (not is_data_from_today) and (
                    stale_count >= max(2, int(total_apis * 0.5))
                )

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
                # Reset alert tracking khi data fresh trở lại
                if display_name in self.last_alert_times:
                    self.logger_api.info(
                        f"Data của {display_name} đã có dữ liệu mới, reset tracking và sẵn sàng gửi alert nếu lỗi lại"
                    )
                    del self.last_alert_times[display_name]
                # Reset stale tracking
                if display_name in self.first_stale_times:
                    del self.first_stale_times[display_name]

            self.logger_api.info(
                f"Kiểm tra API {display_name} - {'Có dữ liệu mới' if is_fresh else 'Dữ liệu cũ'}"
            )

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
                # Chỉ resolve symbols khi chưa có trong cache hoặc config thay đổi
                # SymbolResolverUtil đã có cache 24h cho DISTINCT query
                if api_name not in self.symbols_cache:
                    symbols = SymbolResolverUtil.resolve_api_symbols(
                        api_name, api_config
                    )
                    self.symbols_cache[api_name] = symbols
                else:
                    symbols = self.symbols_cache[api_name]

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

                    # Cleanup symbols cache cho API đã bị remove
                    api_name = item_name.split("-")[0]
                    if api_name not in config_api and api_name in self.symbols_cache:
                        del self.symbols_cache[api_name]
                        self.logger_api.info(f"Đã xóa symbols cache cho {api_name}")

            # Start task mới - dùng symbols từ class cache
            for api_name, api_config in config_api.items():
                # Lấy symbols từ class cache (đã resolve ở trên)
                symbols = self.symbols_cache.get(api_name)

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
