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

            valid_schedule = schedule_cfg

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

            # Tính adjusted overdue nếu có time_ranges
            active_start_time = DataValidator.get_active_start_time(
                schedule_cfg.get("time_ranges") or [], datetime.now()
            )

            if active_start_time and schedule_cfg.get("time_ranges"):
                overdue_seconds = DataValidator.calculate_adjusted_overdue(
                    dt_record_pointer_data_with_column_to_check,
                    datetime.now(),
                    schedule_cfg.get("time_ranges", []),
                )
                is_fresh = overdue_seconds <= allow_delay

            current_time = datetime.now()
            current_date = current_time.strftime("%Y-%m-%d")

            if is_fresh:
                # Reset tracking
                self.tracker.reset_fresh_data(display_name)

                self.logger_api.info(f"Kiểm tra API {display_name} - Có dữ liệu mới")
                await asyncio.sleep(check_frequency)
                continue

            time_str = DataValidator.format_time_overdue(overdue_seconds, allow_delay)

            # Lấy ngày của data mới nhất
            latest_data_date = dt_record_pointer_data_with_column_to_check.strftime(
                "%Y-%m-%d"
            )
            is_data_from_today = latest_data_date == current_date

            # CASE 2: Data STALE - Alert normally (no max_stale suppression)
            stale_count = self.tracker.get_stale_count()
            total_apis = max(stale_count, 1)

            # Nội dung cảnh báo đồng bộ giữa log và alert
            warning_message = f"CẢNH BÁO: Dữ liệu quá hạn {time_str} cho {display_name}"
            self.logger_api.warning(warning_message)

            should_send_alert = self.tracker.should_send_alert(
                display_name, alert_frequency
            )

            if should_send_alert:
                source_info = {"type": "API", "url": uri}
                self.platform_util.send_alert(
                    api_name=api_name,
                    symbol=symbol,
                    overdue_seconds=overdue_seconds,
                    allow_delay=allow_delay,
                    check_frequency=check_frequency,
                    alert_frequency=alert_frequency,
                    alert_level="warning",
                    error_message=f"Dữ liệu API quá hạn {time_str} cho {display_name}",
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
                # Resolve symbols mỗi lần để luôn lấy từ database
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

            # Start task mới - resolve symbols mỗi lần
            for api_name, api_config in config_api.items():
                # Resolve symbols mỗi lần để luôn lấy từ database
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
