**Tổng quan dự án**

---
clone github:

```bash
git clone https://github.com/adee0210/check-data-project
```

1) Chạy trên Linux:

```bash
./run.sh
```

2) Chạy trên Windows:

```powershell
./run.ps1
```

> Cả hai script sẽ tự động tạo virtual environment và cài đặt requirements nếu chưa có

> Nếu muốn chạy trực tiếp không qua script,tự tạo venv, cài requirements và kích hoạt venv trước khi chạy `python src/main.py`.

---

3) Kiểm tra log: xem thư mục `logs/`.


**CẤU HÌNH CHI TIẾT (`configs/data_sources_config.json`)**


- **api** (object):
  - `enable` (bool): Bật/tắt lấy dữ liệu từ API
  - `url` (string): Endpoint API, có thể chứa `{symbol}`
  - `record_pointer` (int): Vị trí bản ghi trong mảng trả về (0 = mới nhất, -1 = cũ nhất)
  - `column_to_check` (string): Tên trường timestamp trong payload
  - `nested_list` (bool, tùy chọn): true nếu response là nested list

- **database** (object):
  - `enable` (bool): Bật/tắt kiểm tra DB
  - `type` / `engine` (string): Loại DB, ví dụ `mongodb`, `postgresql`
  - `database` (string): Tên database/schema
  - `collection_name` or `table` (string): Tên collection/table
  - `column_to_check` (string): Trường thời gian để kiểm tra
  - `record_pointer` (int, tùy chọn): 0 = newest, -1 = oldest

- **disk** (object):
  - `enable` (bool): Bật/tắt kiểm tra file
  - `file_path` (string): Đường dẫn file, có thể dùng `{symbol}`
  - `file_type` (string): Loại file: `json`, `csv`, `txt`, `mtime`
  - `record_pointer` (int, tùy chọn)
  - `column_to_check` (string, tùy chọn)

- **symbols** (object):
  - `auto_sync` (bool|null):
    - true: tự động lấy distinct symbol từ DB
    - false: dùng danh sách tĩnh `values`
    - null: không dùng symbol
  - `values` (array, tùy chọn): Danh sách symbol tự chỉnh nếu không auto_sync
  - `column` (string): Tên cột để lấy distinct symbol khi sử dụng auto_sync

- **check** (object):
  - `timezone_offset` (int): Giờ lệch so với UTC (giây, mặc định 25200 cho UTC+7)
  - `allow_delay` (int, seconds): Giới hạn thời gian data cũ cho phép
  - `check_frequency` (int, seconds): Tần số check data
  - `alert_frequency` (int, seconds): Tần số gửi Log lên Discord/Telegram
  - `max_stale_seconds` (int|null): Giới hạn data cũ để không gửi Log lên Discord/Telegram nữa

- **schedule** (object):
  - `valid_days` (array|null): [0..6], 0 = Thứ Hai -> 6 = Chủ nhật
  - `time_ranges` (string|array|null): null = 24/7, hoặc "HH:MM-HH:MM" hoặc danh sách, Thời gian đứng ở trước < thời gian sau.

**Lưu ý:**
- Nếu chỉ cần check API (ví dụ `gold-data`), chỉ cần phần `api`; phần `database` và `disk` có thể bỏ qua.
- `symbols.auto_sync=true` yêu cầu phải cấu hình đúng phần `database` và `symbols.column`. Nếu không, resolver trả về `[]` và task bị bỏ qua.
- `record_pointer`: Vị trí bản ghi trong mảng trả về từ API/DB. `0` thường là bản ghi mới nhất, `-1` là bản ghi cũ nhất.
- `nested_list=true`: Dùng khi API trả về nested list (ví dụ `[[{...},...]]` hoặc `data: [[...]]`).

Ví dụ tổng hợp (api + db + symbols auto-sync):

```json
{
  "cmc": {
    "api": {
      "enable": true,
      "url": "http://.../cmc/?symbol={symbol}&day=0",
      "record_pointer": 0,
      "column_to_check": "datetime"
    },
    "database": {
      "enable": true,
      "type": "mongodb",
      "database": "cmc_db",
      "collection_name": "cmc",
      "column_to_check": "datetime"
    },
    "symbols": {
      "auto_sync": true,
      "column": "symbol"
    },
    "check": {
      "timezone_offset": 0,
      "allow_delay": 1800,
      "check_frequency": 60,
      "alert_frequency": 60
    }
  }
}
```

**MODULES & LUỒNG XỬ LÝ**

- `src/main.py` — đọc config, khởi logger, tạo asyncio tasks cho từng checker, xử lý signal (shutdown/cleanup).
- `src/check/check_api.py` — `CheckAPI`:
  - Lấy symbols (`SymbolResolverUtil`);
  - Gọi API (theo symbol nếu cần);
  - Lấy `time_field`, parse (`ConvertDatetimeUtil`), so sánh với giờ hiện tại (`TimeValidator`);
  - `AlertTracker` quyết định gửi hay ngưng gửi;
  - `PlatformManager` gửi alert qua Discord/Telegram.
- `src/check/check_database.py` — `CheckDatabase`:
  - Dùng `DatabaseManager` để lấy connector (Mongo/Postgres);
  - Thực hiện query để lấy timestamp (MAX/MIN) theo `record_pointer`;
  - Áp cùng luồng validate/alert.
- `src/check/check_disk.py` — `CheckDisk`:
  - Đọc file (json/csv/txt hoặc mtime), parse datetime, áp luồng validate/alert.
- `src/utils/*`:
  - `LoadConfigUtil`: đọc config với caching theo mtime;
  - `SymbolResolverUtil`: resolve và cache symbols vào `cache/`;
  - `ConvertDatetimeUtil`: parse ISO, epoch, custom format;
  - `TimeValidator`: kiểm tra schedule (UTC+7 mặc định);
  - `AlertTracker`: theo dõi last alert, avoid spam;
  - `PlatformManager`: tạo và gửi tới notifier.

**VẬN HÀNH & TROUBLESHOOTING**

- Logs: kiểm tra `logs/` để xem chi tiết lỗi.
- Nếu không nhận được alert: kiểm tra `configs/common_config.json` (webhook/token/chat_id) và trạng thái `is_primary` trong cấu hình platform.
- Để test nhanh: giảm `check.allow_delay` hoặc `check.check_frequency` cho nguồn cần check.

**Sơ đồ kiến trúc**

Quan hệ chính giữa các module:

- `src/main.py` -> khởi chạy các tác vụ bất đồng bộ -> {`CheckAPI`, `CheckDatabase`, `CheckDisk`}
- `CheckAPI` -> sử dụng -> {`LoadConfigUtil`, `SymbolResolverUtil`, `ConvertDatetimeUtil`, `TimeValidator`, `DataValidator`, `AlertTracker`, `PlatformManager`}
- `CheckDatabase` -> sử dụng -> {`DatabaseManager` -> (`MongoDBConnector`, `PostgreSQLConnector`), `ConvertDatetimeUtil`, `TimeValidator`, `DataValidator`, `AlertTracker`, `PlatformManager`}
- `CheckDisk` -> sử dụng -> {`ConvertDatetimeUtil`, `TimeValidator`, `DataValidator`, `AlertTracker`, `PlatformManager`}


Utils:
- `LoadConfigUtil`: load file cấu hình JSON, caching và auto-reload khi file thay đổi
- `SymbolResolverUtil`: danh sách `symbols` (cache vào `/cache` trong 24h)
- `ConvertDatetimeUtil`: parse và chuyển đổi các dạng datetime
- `AlertTracker`: quản lý trạng thái alert (frequency, silent mode, low-activity...)
- `TaskManager`: helper tạo và chạy asyncio tasks

Lớp platform (gửi thông báo):
- `PlatformManager` tạo các notifier {`DiscordNotifier`, `TelegramNotifier`} từ `configs/common_config.json`.

Lớp database:
- `configs/database_config/*`: `BaseDatabaseConnector`, `MongoDBConnector`, `PostgreSQLConnector` và `DatabaseManager` (factory + cache connector).

**Các file chính, lớp và phương thức**

- `src/check/check_api.py`
    - `__init__`: khởi tạo logger, `TaskManager`, `PlatformManager`, cache symbols, `AlertTracker`.
    - `_load_config()`: load `data_sources_config.json` và lọc các mục có `api.enable = true`.
    - `check_data_api(api_name, api_config, symbol)`: vòng lặp async. Luồng xử lý:
      - Dùng `AlertTracker` quyết định gửi alert / tránh spam
      - Gọi `PlatformManager.send_alert(...)` để gửi tới các platform primary
    - Sử dụng `DatabaseManager` để tạo/get connector và `query()` lấy timestamp bản ghi mới nhất/cũ nhất
    - `run_database_tasks()` quản lý các task cho mỗi database hoặc mỗi symbol.

- `src/check/check_disk.py`
    - `run_disk_tasks()` quản lý task cho từng file hoặc symbol
- `src/logic_check/data_validator.py`
  - Lớp: `DataValidator`
    - `is_data_fresh(data_datetime, allow_delay)` trả về `(is_fresh, overdue_seconds)`. Có xử lý đặc biệt khi dữ liệu chỉ có ngày (date-only).
- `src/utils/load_config_util.py`
  - Lớp: `LoadConfigUtil` quản lý đọc file JSON với caching dựa trên `mtime` và khả năng reload khi file thay đổi.

- `src/utils/symbol_resolver_util.py`
  - Lớp: `SymbolResolverUtil` giải quyết danh sách symbol theo config `symbols.auto_sync`:
    - `auto_sync = true`: tự động lấy distinct symbols từ database có cùng `api_name` (qua `DatabaseManager`), cache vào `/cache/symbols_{api}.json` trong 24 giờ.
    - `auto_sync = false`: dùng `symbols.values` từ cấu hình.
    - `auto_sync = null` hoặc không có: API không cần symbol.

- `src/utils/task_manager_util.py`
  - Lớp: `TaskManager` helper tạo và chạy các asyncio task.

- Platform utilities (`src/utils/platform_util/`)
  - `base_platform.py`: `BasePlatformNotifier` interface + helper `build_base_message_data()`
  - `discord_util.py`: `DiscordNotifier` (gửi qua webhook Discord, mong response 204 thành công)
  - `telegram_util.py`: `TelegramNotifier` (gửi qua Telegram Bot API, parse Markdown)
  - `platform_manager.py`: `PlatformManager` tạo notifier từ `configs/common_config.json` và expose `send_alert()` gửi tới tất cả platform primary.

- Database connectors (`configs/database_config/`)
  - `base_db.py`: `BaseDatabaseConnector` interface (connect, query, close, get_required_package)
  - `mongo_config.py`: `MongoDBConnector` dùng `pymongo` (connect, query, get_distinct_symbols)
  - `postgres_config.py`: `PostgreSQLConnector` dùng `psycopg2` (connect, query với MAX/MIN, get_distinct_symbols)
  - `database_manager.py`: `DatabaseManager` (factory, cache connectors, merge credential từ `common_config.json`).

**Luồng hoạt động**

- `src/main.py` khởi song song `CheckAPI`, `CheckDatabase`, `CheckDisk`.
- Mỗi checker load config động từ `data_sources_config.json` (qua `LoadConfigUtil`) và tạo/cancel tasks theo config.
- `SymbolResolverUtil` giải quyết symbol (auto-sync từ DB hoặc dùng giá trị thủ công).
- `DatabaseManager` quản lý kết nối DB, delegating tới `MongoDBConnector` hoặc `PostgreSQLConnector` để query timestamp.
- `AlertTracker` kiểm soát tần suất gửi alert, silent mode, low-activity detection.
- `PlatformManager` gửi thông báo tới các platform được đánh dấu `is_primary` trong `common_config.json`.