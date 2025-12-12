import asyncio
from datetime import datetime

import requests
from utils.convert_datetime_util import ConvertDatetimeUtil
from logic_check.time_validator import TimeValidator
from logic_check.data_validator import DataValidator
from utils.alert_tracker_util import AlertTracker

from configs.logging_config import LoggerConfig
from utils.task_manager_util import TaskManager
from utils.load_config_util import LoadConfigUtil
from utils.platform_util.platform_manager import PlatformManager
from utils.symbol_resolver_util import SymbolResolverUtil


class CheckAPI:
    """Class kiểm tra data freshness từ API endpoints"""

    def __init__(self):
        self.logger_api = LoggerConfig.logger_config("CheckAPI", "api.log")
        self.task_manager_api = TaskManager()
        self.platform_util = PlatformManager()

        # Symbols cache ở class level để persist qua các reload
        # Format: {api_name: symbols_list}
        self.symbols_cache = {}

        # Sử dụng AlertTracker để quản lý tất cả tracking
        self.tracker = AlertTracker()

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
        # Tạo display name trước
        if symbol:
            display_name = f"{api_name}-{symbol}"
        else:
            display_name = api_name

        while True:
            # Reload config mỗi lần loop để nhận config mới
            # (LoadConfigUtil có cache, chỉ reload khi file thay đổi)
            all_config = self._load_config()
            api_config = all_config.get(api_name, api_config)

            # Đọc config từ cấu trúc mới
            api_cfg = api_config.get("api", {})
            check_cfg = api_config.get("check", {})
            schedule_cfg = api_config.get("schedule", {})
            symbols_cfg = api_config.get("symbols", {})

            uri = api_cfg.get("url")
            record_pointer = api_cfg.get("record_pointer", 0)
            column_to_check = api_cfg.get("column_to_check", "datetime")
            nested_list = api_cfg.get("nested_list", False)  # True nếu API trả [[...]]

            timezone_offset = check_cfg.get("timezone_offset", 7)
            allow_delay = check_cfg.get("allow_delay", 60)
            alert_frequency = check_cfg.get("alert_frequency", 60)
            check_frequency = check_cfg.get("check_frequency", 10)
            max_stale_seconds = check_cfg.get("max_stale_seconds", None)

            valid_schedule = schedule_cfg
            holiday_grace_period = check_cfg.get("holiday_grace_period", 2 * 3600)

            if symbol:
                uri = uri.format(symbol=symbol)

            # Kiểm tra valid_schedule: chỉ check trong khoảng thời gian và ngày được phép
            is_within_schedule = TimeValidator.is_within_valid_schedule(
                valid_schedule, timezone_offset
            )

            if not is_within_schedule:
                # Chỉ log 1 lần khi vào trạng thái ngoài giờ
                if not self.tracker.outside_schedule_logged.get(display_name, False):
                    self.logger_api.info(
                        f"Ngoài lịch kiểm tra cho {display_name}, tạm dừng..."
                    )
                    self.tracker.outside_schedule_logged[display_name] = True

                await asyncio.sleep(60)
                continue
            else:
                # Reset flag khi vào lại trong giờ
                if self.tracker.outside_schedule_logged.get(display_name, False):
                    self.logger_api.info(
                        f"Trong lịch kiểm tra cho {display_name}, tiếp tục..."
                    )
                    self.tracker.outside_schedule_logged[display_name] = False

            try:
                r = requests.get(url=uri, timeout=10)
                r.raise_for_status()

                response = r.json()

                # Xác định data_array dựa vào nested_list
                if nested_list:
                    # Response format: [[{...}, {...}]]
                    # Hoặc với wrapper: {"code": 200, "data": [[{...}]]}
                    if isinstance(response, dict):
                        # Có wrapper (code, message, data)
                        response_code = response.get("code", 200)
                        if response_code != 200:
                            raise ValueError(
                                f"Response code = {response_code} (không phải 200)"
                            )

                        # Lấy data từ các key phổ biến (ưu tiên 'data' trước)
                        if "data" in response:
                            data_array = response["data"]
                        elif "result" in response:
                            data_array = response["result"]
                        else:
                            raise KeyError("Response không có key 'data' hoặc 'result'")
                    else:
                        # Response trực tiếp là array
                        data_array = response

                    # Kiểm tra data_array có phải list không
                    if not isinstance(data_array, list):
                        raise TypeError(
                            f"Response không phải list, là {type(data_array).__name__}"
                        )

                    # Nested list: [[...]] -> [...]
                    if len(data_array) == 0:
                        raise ValueError("EMPTY_DATA")

                    if not isinstance(data_array[0], list):
                        raise TypeError(
                            f"Nested list expected nhưng phần tử đầu tiên không phải list"
                        )

                    # Flatten
                    data_array = data_array[0]

                    if not isinstance(data_array, list):
                        raise TypeError(f"Nested array sau flatten không phải list")

                else:
                    # Response format: [{...}, {...}]
                    # Hoặc với wrapper: {"code": 200, "data": [{...}]}
                    if isinstance(response, dict):
                        # Có wrapper
                        response_code = response.get("code", 200)
                        if response_code != 200:
                            raise ValueError(
                                f"Response code = {response_code} (không phải 200)"
                            )

                        # Lấy data từ các key phổ biến (ưu tiên 'data' trước)
                        if "data" in response:
                            data_array = response["data"]
                        elif "result" in response:
                            data_array = response["result"]
                        else:
                            raise KeyError("Response không có key 'data' hoặc 'result'")
                    else:
                        # Response trực tiếp là array
                        data_array = response

                    # Kiểm tra data_array có phải list không
                    if not isinstance(data_array, list):
                        raise TypeError(
                            f"Response không phải list, là {type(data_array).__name__}"
                        )

                # Kiểm tra mảng rỗng + code=200 → WARNING (chưa có data vào thời điểm này)
                if len(data_array) == 0:
                    raise ValueError("EMPTY_DATA")

                # Kiểm tra record_pointer hợp lệ
                if record_pointer >= len(data_array):
                    raise IndexError(
                        f"record_pointer {record_pointer} vượt quá độ dài mảng {len(data_array)}"
                    )

                # Lấy record theo pointer
                target_record = data_array[record_pointer]

                # Kiểm tra target_record có phải dict không
                if not isinstance(target_record, dict):
                    raise TypeError(
                        f"Record tại pointer {record_pointer} không phải dict, là {type(target_record).__name__}"
                    )

                # Lấy giá trị column_to_check
                if column_to_check not in target_record:
                    raise KeyError(f"Record không có column '{column_to_check}'")

                record_pointer_data_with_column_to_check = target_record[
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
            except ValueError as e:
                error_str = str(e)
                # Code != 200 hoặc lỗi giá trị khác → ERROR
                if "Response code" in error_str:
                    error_message = error_str
                    error_type = "API"
                    api_error = True
                    self.logger_api.error(
                        f"Lỗi API: {error_message} cho {display_name}"
                    )
                # Mảng rỗng + code=200 → WARNING (chưa có data vào thời điểm này)
                elif "EMPTY_DATA" in error_str:
                    error_message = "Chưa có dữ liệu vào thời điểm này"
                    error_type = "API_WARNING"
                    api_error = True

                    # Track empty data để phát hiện pattern và chuyển silent mode
                    is_silent, duration = self.tracker.track_empty_data(
                        display_name, silent_threshold_seconds=1800
                    )

                    if is_silent and duration is not None:
                        self.logger_api.warning(
                            f"[EMPTY_DATA] {display_name} liên tục empty data trong {int(duration/60)} phút. "
                            f"Chuyển silent mode - chỉ log, không gửi alert nữa."
                        )

                    self.logger_api.warning(
                        f"Cảnh báo API: {error_message} cho {display_name}"
                    )
                else:
                    error_message = f"Lỗi giá trị - {error_str}"
                    error_type = "API"
                    api_error = True
                    self.logger_api.error(
                        f"Lỗi API: {error_message} cho {display_name}"
                    )
            except (KeyError, IndexError, TypeError) as e:
                # Format sai - đây mới là ERROR thật sự
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

                # Kiểm tra xem có đang trong silent mode cho EMPTY_DATA không
                if error_type == "API_WARNING":
                    is_silent, _ = self.tracker.track_empty_data(
                        display_name, silent_threshold_seconds=0
                    )
                    if is_silent:
                        # Silent mode - chỉ log, không gửi alert
                        self.logger_api.debug(
                            f"[EMPTY_DATA SILENT] {display_name} vẫn empty data, skip alert (silent mode)"
                        )
                        await asyncio.sleep(check_frequency)
                        continue

                should_send_alert = self.tracker.should_send_alert(
                    display_name, alert_frequency
                )

                if should_send_alert:
                    # Build source_info với API URL
                    source_info = {"type": "API", "url": uri}

                    # Xác định alert_level dựa vào error_type
                    if error_type == "API_WARNING":
                        alert_level = "warning"
                    else:
                        alert_level = "error"

                    self.platform_util.send_alert(
                        api_name=api_name,
                        symbol=symbol,
                        overdue_seconds=0,
                        allow_delay=allow_delay,
                        check_frequency=check_frequency,
                        alert_frequency=alert_frequency,
                        alert_level=alert_level,
                        error_message=error_message,
                        error_type=error_type,
                        source_info=source_info,
                    )
                    self.tracker.record_alert_sent(display_name)

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

            current_time = datetime.now()
            current_date = current_time.strftime("%Y-%m-%d")

            # Reset empty_data_tracking nếu API trả về data thành công
            duration = self.tracker.reset_empty_data(display_name)
            if duration is not None:
                self.logger_api.info(
                    f"[EMPTY_DATA RESOLVED] {display_name} đã có data sau {int(duration/60)} phút empty. Reset tracking."
                )

            # ===== EARLY CHECK: Low-activity symbol - chỉ log, không gửi alert =====
            if self.tracker.is_low_activity(display_name):
                if is_fresh:
                    # Data mới xuất hiện - log nhưng KHÔNG xóa khỏi low_activity
                    # (vì đã xác định là giao dịch thấp)
                    self.logger_api.info(
                        f"[LOW-ACTIVITY] {display_name} có data mới nhưng vẫn được đánh dấu low-activity, không gửi alert"
                    )
                else:
                    self.logger_api.debug(
                        f"[LOW-ACTIVITY] {display_name} không có data mới, skip alert"
                    )
                await asyncio.sleep(check_frequency)
                continue

            # ===== CASE 1: Data FRESH - Reset tất cả tracking =====
            if is_fresh:
                # Reset tracking
                if self.tracker.is_in_silent_mode(display_name):
                    self.logger_api.info(f"{display_name} có data mới, reset tracking")

                self.tracker.reset_fresh_data(display_name)

                self.logger_api.info(f"Kiểm tra API {display_name} - Có dữ liệu mới")
                await asyncio.sleep(check_frequency)
                continue

            # ===== CASE 2: Data STALE - Xử lý phức tạp =====
            time_str = DataValidator.format_time_overdue(overdue_seconds, allow_delay)

            # Lấy ngày của data mới nhất
            latest_data_date = dt_record_pointer_data_with_column_to_check.strftime(
                "%Y-%m-%d"
            )
            is_data_from_today = latest_data_date == current_date

            # Check nếu vượt max_stale_seconds
            total_stale_seconds = overdue_seconds + allow_delay
            exceeds_max_stale, is_first_time = self.tracker.track_stale_data(
                display_name, max_stale_seconds, total_stale_seconds
            )

            # ===== CASE 2A: Vượt max_stale_seconds =====
            if exceeds_max_stale:
                # Gửi alert 1 lần duy nhất
                if is_first_time:
                    hours = int(total_stale_seconds // 3600)
                    minutes = int((total_stale_seconds % 3600) // 60)
                    seconds = int(total_stale_seconds % 60)

                    max_hours = int(max_stale_seconds // 3600)
                    max_minutes = int((max_stale_seconds % 3600) // 60)
                    max_seconds = int(max_stale_seconds % 60)

                    self.logger_api.warning(
                        f"Data của {display_name} đã cũ {hours} giờ {minutes} phút {seconds} giây "
                        f"(vượt ngưỡng {max_hours} giờ {max_minutes} phút {max_seconds} giây). "
                        f"Gửi alert cuối cùng, sau đó chỉ log."
                    )

                    status_message = f"Data quá cũ (vượt {max_hours} giờ {max_minutes} phút {max_seconds} giây), không có data mới, dừng gửi thông báo"

                    source_info = {"type": "API", "url": uri}

                    self.platform_util.send_alert(
                        api_name=api_name,
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
                    self.tracker.record_alert_sent(display_name)
                else:
                    # Đã gửi alert rồi - chỉ log
                    self.logger_api.info(
                        f"[SILENT MODE] {display_name} vẫn không có data, chỉ log (không gửi alert)"
                    )

                # Track consecutive stale days để phát hiện low-activity
                consecutive_days, became_low_activity = (
                    self.tracker.track_consecutive_stale_days(
                        display_name, low_activity_threshold_days=2
                    )
                )

                if became_low_activity:
                    self.logger_api.warning(
                        f"[LOW-ACTIVITY DETECTED] {display_name} đã {consecutive_days} ngày liên tiếp không có data. "
                        f"Đánh dấu là giao dịch thấp, dừng gửi alert vĩnh viễn."
                    )

            # ===== CASE 2B: Chưa vượt max_stale - Alert bình thường =====
            else:
                # Đếm số API stale để phát hiện ngày lễ
                stale_count = self.tracker.get_stale_count()
                total_apis = max(stale_count, 1)

                is_suspected_holiday = self.tracker.check_holiday_pattern(
                    current_date, is_data_from_today, total_apis
                )

                self.logger_api.warning(
                    f"CẢNH BÁO: Dữ liệu quá hạn {time_str} cho {display_name}"
                    f"{' (Nghi ngờ ngày lễ)' if is_suspected_holiday else ''}"
                )

                # Kiểm tra alert_frequency
                should_send_alert = self.tracker.should_send_alert(
                    display_name, alert_frequency
                )

                if should_send_alert:
                    if is_suspected_holiday:
                        # Chỉ gửi alert ngày lễ 1 lần mỗi ngày
                        if self.tracker.last_holiday_alert_date != current_date:
                            context_message = (
                                f"Nghi ngờ ngày nghỉ lễ (có {stale_count}/{total_apis} API đang thiếu data). "
                                f"Nếu đúng là ngày lễ, vui lòng bỏ qua cảnh báo này."
                            )
                            source_info = {"type": "API", "url": uri}

                            self.platform_util.send_alert(
                                api_name=api_name,
                                symbol=symbol,
                                overdue_seconds=overdue_seconds,
                                allow_delay=allow_delay,
                                check_frequency=check_frequency,
                                alert_frequency=alert_frequency,
                                alert_level="warning",
                                error_message=context_message,
                                source_info=source_info,
                            )
                            self.tracker.record_alert_sent(display_name)
                            self.tracker.last_holiday_alert_date = current_date
                            self.logger_api.info(
                                f"Đã gửi alert ngày lễ cho {display_name}"
                            )
                        else:
                            self.logger_api.info(
                                f"Đã gửi alert ngày lễ hôm nay, skip để tránh spam"
                            )
                    else:
                        # Alert bình thường
                        source_info = {"type": "API", "url": uri}

                        self.platform_util.send_alert(
                            api_name=api_name,
                            symbol=symbol,
                            overdue_seconds=overdue_seconds,
                            allow_delay=allow_delay,
                            check_frequency=check_frequency,
                            alert_frequency=alert_frequency,
                            alert_level="warning",
                            error_message="Không có dữ liệu mới",
                            source_info=source_info,
                        )
                        self.tracker.record_alert_sent(display_name)

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
