<!-- README for check-data-project - Clean and Pretty -->
# Check Data Project — Giám sát tính cập nhật dữ liệu

Phiên bản ngắn gọn: hướng dẫn cài đặt, cấu hình nhanh và các quy tắc alert chính.

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Yêu cầu & Cài đặt](#yêu-cầu--cài-đặt)
- [Cấu hình nhanh](#cấu-hình-nhanh)
- [Chạy hệ thống](#chạy-hệ-thống)
- [Quy tắc cảnh báo](#quy-tắc-cảnh-báo)
- [Ví dụ cấu hình](#ví-dụ-cấu-hình)
- [Mở rộng](#mở-rộng)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [License](#license)

---

## Tổng quan

`check-data-project` giám sát tính cập nhật của dữ liệu từ:
- **API** (JSON)
- **Database** (MongoDB, PostgreSQL)
- **Disk files** (JSON/CSV/TXT/mtime)

Hệ thống gửi alert qua **Discord/Telegram** (cấu hình trong `configs/common_config.json`).

**Điểm nổi bật:**
- Thêm lớp `AlertTracker` tại `src/utils/alert_tracker_util.py` để quản lý trạng thái alert chung: tracking `empty data`, `silent mode` khi vượt `max_stale_seconds`, `low-activity` detection, alert frequency và holiday pattern. Các checker (`check_api`, `check_database`, `check_disk`) sử dụng lớp này để đảm bảo hành vi thống nhất.
- Ngưỡng stale hiện dùng `seconds` thay vì `days` (`max_stale_seconds`).

---

## Yêu cầu & Cài đặt

- **Python**: 3.8+
- **Cài đặt tự động**: Script `run.ps1` (Windows) hoặc `run.sh` (Linux/macOS) sẽ tự động tạo virtual environment và cài đặt packages khi chạy lần đầu.

### Windows PowerShell
```powershell
git clone https://github.com/adee0210/check-data-project
cd check_data_project
.\run.ps1 start  # Tự động tạo .venv và cài đặt packages
```

### Linux / macOS
```bash
git clone https://github.com/adee0210/check-data-project
cd check_data_project
./run.sh start  # Tự động tạo .venv và cài đặt packages
```

---

## Cấu hình nhanh

Cấu hình nằm trong `configs/data_sources_config.json`.

### Các key quan trọng (tất cả đơn vị **giây**)
- `check.allow_delay` — độ trễ cho phép
- `check.check_frequency` — tần suất kiểm tra
- `check.alert_frequency` — tần suất gửi alert (tránh spam)
- `check.max_stale_seconds` — giới hạn stale trước khi gửi final alert
- `api.nested_list` — đặt `true` nếu API trả `data` dạng list-nested (ví dụ: `{"data": [[...]]}`)

**Lưu ý:** Thay đổi cấu hình sẽ được áp dụng tự động khi hệ thống reload (cơ chế reload động).

---

## Chạy hệ thống

### Windows PowerShell
```powershell
.\run.ps1 start
.\run.ps1 status
.\run.ps1 restart
.\run.ps1 stop
```

### Linux / macOS
```bash
./run.sh start
./run.sh status
./run.sh restart
./run.sh stop
./run.sh logs    # Xem log
./run.sh health  # Kiểm tra tình trạng hệ thống
```

### Chạy trực tiếp (Development)
```bash
source .venv/bin/activate
python src/main.py
```

### Xem logs
```bash
tail -f logs/main.log
tail -f logs/api.log
tail -f logs/database.log
```

---

## Quy tắc cảnh báo

- **Mức cảnh báo**: `ERROR` (đỏ), `WARNING` (cam), `INFO` (xanh lá).
- **API**:
  - `code != 200` hoặc JSON sai cấu trúc → `ERROR`
  - `code == 200` & `data == []` → `WARNING` (Empty-data behavior)
  - Sử dụng `api.nested_list: true` nếu API trả `data` dạng lồng list
- **Database**:
  - Nếu query trả `None` hoặc không có bản ghi mới → coi là `EMPTY_DATA`

### Empty-data behavior (quan trọng)
Khi một nguồn (API / Database / Disk) trả về empty data (`data==[]` hoặc DB `None`), hệ thống sẽ gửi **một cảnh báo `WARNING` duy nhất**, sau đó chuyển sang **silent mode** ngay để tránh spam. Việc quản lý này được thực hiện bởi lớp `AlertTracker` (`src/utils/alert_tracker_util.py`).

### Stale behavior
- Nếu dữ liệu cũ hơn `max_stale_seconds`, hệ thống sẽ gửi một final alert, sau đó giảm spam (silent mode) cho nguồn đó. Task vẫn tiếp tục chạy để ghi nhận khi data trở lại.

### Low-activity detection
- Nếu một symbol liên tục stale trong nhiều ngày (threshold mặc định = 2 ngày), hệ thống có thể đánh dấu là `low-activity` và tạm ngưng gửi alert cho symbol đó. Hiện trạng low-activity chưa được lưu persistent across restarts.

## Ví dụ cấu hình

-   `enable`: Bật/tắt kiểm tra API
-   `url`: API endpoint, có thể dùng `{symbol}` placeholder
-   `record_pointer`: `"first"` = record đầu tiên, `"last"` = record cuối cùng
-   `column_to_check`: Field chứa timestamp trong JSON response

**database section:**

-   `enable`: Bật/tắt kiểm tra database
-   `type`: `"mongodb"` hoặc `"postgresql"`
-   `collection_name`: Tên collection (MongoDB)
-   `table`: Tên table (PostgreSQL)
-   `record_pointer`: `"first"` = MIN value, `"last"` = MAX value
-   `column_to_check`: Column chứa timestamp

**disk section:** *(NEW)*

-   `enable`: Bật/tắt kiểm tra file trên disk
-   `file_type`: `"json"`, `"csv"`, `"txt"`, hoặc `"mtime"` (modification time)
-   `file_path`: Đường dẫn đầy đủ đến file (có thể dùng `{symbol}` placeholder)
-   `record_pointer`: `"first"` = record đầu tiên, `"last"` = record cuối cùng
-   `column_to_check`: Column/key chứa timestamp (bỏ qua nếu `file_type="mtime"`)

**symbols section:**

-   `auto_sync`: `true` = tự động lấy từ DB, `false` = dùng manual list, `null` = không cần
-   `values`: Array symbols nếu `auto_sync=false`
-   `column`: Column chứa symbol

**check section:**

-   `timezone_offset`: Offset timezone (0=UTC, 7=GMT+7)
-   `allow_delay`: Độ trễ tối đa cho phép (giây)
-   `check_frequency`: Tần suất check (giây)
-   `alert_frequency`: Tần suất alert (giây) - tránh spam
-   `max_stale_days`: Dừng task khi data cũ quá X ngày (smart holiday detection)

**schedule section:**

-   `valid_days`: Array ngày (0=Mon, 6=Sun), `null` = all days
-   `time_ranges`: Array khung giờ HH:MM-HH:MM, `null` = 24/7

### 3.3. Ví Dụ Cấu Hình

#### 1. API + Database
>>>>>>> 6342fad4541a6f43092b52b6892311d378867ee1

### 1. Disk JSON multi-symbol
```json
{
  "stock-prices": {
    "disk": {
      "enable": true,
      "file_type": "json",
      "file_path": "/data/{symbol}_prices.json",
      "record_pointer": "last",
      "column_to_check": "updated_at"
    },
    "symbols": {
      "auto_sync": false,
      "values": ["AAPL", "GOOGL", "MSFT"],
      "column": null
    },
    "check": {
      "timezone_offset": 7,
      "allow_delay": 60,
      "check_frequency": 60,
      "alert_frequency": 300,
      "max_stale_seconds": 86400
    },
    "schedule": {
      "valid_days": [0,1,2,3,4],
      "time_ranges": ["09:00-11:30","13:00-15:00"]
    }
  }
}
```

### 2. API với nested list
```json
{
  "example-api": {
    "api": {
      "enable": true,
      "url": "https://api.example.com/data?symbol={symbol}",
      "record_pointer": "last",
      "column_to_check": "timestamp",
      "nested_list": true
    },
    "check": {
      "allow_delay": 120,
      "check_frequency": 30,
      "alert_frequency": 300,
      "max_stale_seconds": 300
    }
  }
}
```

---

## Mở rộng

### Thêm Database mới (MySQL)

1. **Tạo connector** (`configs/database_config/mysql_config.py`):
```python
from .base_db import BaseDatabaseConnector

class MySQLConnector(BaseDatabaseConnector):
    def connect(self, config):
        import mysql.connector
        return mysql.connector.connect(**config)
    
    def query(self, config, symbol=None):
        # Query logic here
        pass
    
    def get_required_package(self):
        return "mysql-connector-python"
```

2. **Đăng ký** (`configs/database_config/database_manager.py`):
```python
CONNECTOR_REGISTRY = {
    "mongodb": MongoDBConnector,
    "postgresql": PostgreSQLConnector,
    "mysql": MySQLConnector  # Add this
}
```

3. **Cấu hình** (`configs/common_config.json`):
```json
{
  "MYSQL_CONFIG": {
    "host": "localhost",
    "port": 3306,
    "database": "your_db",
    "user": "root",
    "password": "password"
  }
}
```

### Thêm Platform mới (Slack)

1. **Tạo notifier** (`src/utils/platform_util/slack_util.py`):
```python
from .base_platform import BasePlatformNotifier

class SlackNotifier(BasePlatformNotifier):
    def validate_config(self):
        if not self.config.get("webhook_url"):
            raise ValueError("Thiếu 'webhook_url'")
    
    def get_platform_name(self):
        return "Slack"
    
    def send_alert(self, api_name, symbol, overdue_seconds, allow_delay, check_frequency, alert_frequency, alert_level="warning", error_message="Không có dữ liệu mới", error_type=None):
        # Send logic here
        pass
```

2. **Đăng ký** (`src/utils/platform_util/platform_manager.py`):
```python
NOTIFIER_REGISTRY = {
    "discord": DiscordNotifier,
    "telegram": TelegramNotifier,
    "slack": SlackNotifier  # Add this
}
```

3. **Cấu hình** (`configs/common_config.json`):
```json
{
  "PLATFORM_CONFIG": {
    "slack": {
      "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
      "is_primary": true
    }
  }
}
```

---

## Troubleshooting

### Lỗi Connection
- **Nguyên nhân**: Database không chạy hoặc sai config
- **Giải pháp**: Check `systemctl status mongodb` hoặc `psql -h localhost`

### Alert không gửi
- **Kiểm tra**: Logs (`tail -f logs/main.log`), test webhook với curl
- **Nguyên nhân**: `alert_frequency` quá thấp, ngoài `schedule`

### Data cũ nhưng không alert
- **Kiểm tra**: `allow_delay`, `max_stale_seconds`, timezone
- **Nguyên nhân**: Config sai hoặc holiday detection

### Performance issues
- **Giải pháp**: Tăng `check_frequency`, tạo index database, giảm số tasks

---

## FAQ

**Q: Có thể monitor nhiều nguồn trong 1 config?**  
A: Có! Set `enable: true` cho api, database, disk cùng lúc.

**Q: Schedule hoạt động thế nào?**  
A: `valid_days` (0=Mon, 6=Sun), `time_ranges` (HH:MM-HH:MM). `null` = always on.

**Q: alert_frequency khác check_frequency thế nào?**  
A: `check_frequency`: Tần suất CHECK data. `alert_frequency`: Tần suất GỬI alert (tránh spam).

**Q: Có thể dùng placeholder {symbol} ở đâu?**  
A: `api.url`, `disk.file_path`.

---

## License

MIT License

**Author:** adee0210  
**Repository:** [https://github.com/adee0210/check-data-project](https://github.com/adee0210/check-data-project)

## 6. MỞ RỘNG

### 6.1. Thêm Database Mới (MySQL)

#### Bước 1: Tạo Connector

Tạo file `configs/database_config/mysql_config.py`:

```python
"""MySQL Connector"""from typing import Any, Dict, Optionalfrom datetime import datetimefrom .base_db import BaseDatabaseConnectorclass MySQLConnector(BaseDatabaseConnector):    """MySQL connector implementation"""        def __init__(self, logger):        super().__init__(logger)        def connect(self, config: Dict[str, Any]) -> Any:        """Kết nối MySQL"""        try:            import mysql.connector        except ImportError:            raise ImportError(                f"Thiếu thư viện MySQL. "                f"Cài đặt: pip install {self.get_required_package()}"            )                self.validate_config(config, ["host", "database", "username", "password"])                self.connection = mysql.connector.connect(            host=config["host"],            port=config.get("port", 3306),            database=config["database"],            user=config["username"],            password=config["password"]        )                self.logger.info(f"Kết nối MySQL thành công: {config['database']}")        return self.connection        def query(self, config: Dict[str, Any], symbol: Optional[str] = None) -> datetime:        """Query MySQL"""        if not self.is_connected():            raise ConnectionError("Chưa kết nối MySQL")                self.validate_config(config, ["table", "column_to_check"])                table = config["table"]        column = config["column_to_check"]        record_pointer = config.get("record_pointer", 0)        symbol_column = config.get("symbol_column")                agg_func = "MAX" if record_pointer == 0 else "MIN"        query = f"SELECT {agg_func}({column}) FROM {table}"        params = []                if symbol and symbol_column:            query += f" WHERE {symbol_column} = %s"            params.append(symbol)                cursor = self.connection.cursor()        cursor.execute(query, params)        result = cursor.fetchone()        cursor.close()                if result and result[0]:            return result[0]        raise ValueError("Không có kết quả")        def close(self) -> None:        """Đóng connection"""        if self.connection:            self.connection.close()            self.logger.info("Đã đóng MySQL")        self.connection = None        def get_required_package(self) -> str:        return "mysql-connector-python"
```

#### Bước 2: Register

Edit `configs/database_config/database_manager.py`:

```python
# Thêm importfrom .mysql_config import MySQLConnectorclass DatabaseManager:    CONNECTOR_REGISTRY = {        "mongodb": MongoDBConnector,        "postgresql": PostgreSQLConnector,        "mysql": MySQLConnector,  # ← THÊM    }        def _get_connection_config(self, db_type, db_config):        # ... existing code ...                elif db_type == "mysql":  # ← THÊM            mysql_config = common_config["MYSQL_CONFIG"]            return {                "host": mysql_config["host"],                "port": mysql_config["port"],                "database": database_name or mysql_config["database"],                "username": mysql_config["user"],                "password": mysql_config["password"],            }
```

#### Bước 3: Config

Edit `configs/common_config.json`:

```json
{  "MYSQL_CONFIG": {    "host": "localhost",    "port": 3306,    "database": "your_db",    "user": "root",    "password": "password"  }}
```

**XONG!** Sử dụng: `"type": "mysql"` trong config

### 6.2. Thêm Platform Mới (Slack)

#### Bước 1: Tạo Notifier

Tạo file `src/utils/platform_util/slack_util.py`:

```python
"""Slack Notifier"""import requestsfrom typing import Dict, Any, Optionalfrom .base_platform import BasePlatformNotifierclass SlackNotifier(BasePlatformNotifier):    """Slack notifier implementation"""        def validate_config(self) -> None:        """Validate Slack config"""        if not self.config.get("webhook_url"):            raise ValueError("Thiếu 'webhook_url'")        def get_platform_name(self) -> str:        return "Slack"        def send_alert(        self,        api_name: str,        symbol: Optional[str],        overdue_seconds: int,        allow_delay: int,        check_frequency: int,        alert_frequency: int,        alert_level: str = "warning",        error_message: str = "Không có dữ liệu mới",        error_type: Optional[str] = None,    ) -> bool:        """Gửi alert đến Slack"""        if not self.is_enabled():            return False                webhook_url = self.config["webhook_url"]        data = self.build_base_message_data(            api_name, symbol, overdue_seconds, allow_delay,            check_frequency, alert_frequency, alert_level,            error_message, error_type        )                message = self._format_slack_message(data)                try:            response = requests.post(webhook_url, json=message, timeout=10)            if response.status_code == 200:                self.logger.info("Gửi Slack thành công")                return True            return False        except Exception as e:            self.logger.error(f"Lỗi gửi Slack: {e}")            return False        def _format_slack_message(self, data: Dict[str, Any]) -> Dict[str, Any]:        """Format Slack blocks"""        fields = [            {"type": "mrkdwn", "text": f"*Thời gian:*n{data['current_time']}"},            {"type": "mrkdwn", "text": f"*Dữ liệu cũ:*n{data['total_time_formatted']}"},        ]                if data['symbol']:            fields.insert(1, {"type": "mrkdwn", "text": f"*Symbol:*n{data['symbol']}"})                return {            "blocks": [                {                    "type": "header",                    "text": {                        "type": "plain_text",                        "text": f"{data['emoji']} {data['api_name']} - {data['alert_type']}"                    }                },                {"type": "section", "fields": fields}            ]        }
```

#### Bước 2: Register

Edit `src/utils/platform_util/platform_manager.py`:

```python
# Thêm importfrom .slack_util import SlackNotifierclass PlatformManager:    NOTIFIER_REGISTRY = {        "discord": DiscordNotifier,        "telegram": TelegramNotifier,        "slack": SlackNotifier,  # ← THÊM    }
```

#### Bước 3: Config

Edit `configs/common_config.json`:

```json
{  "PLATFORM_CONFIG": {    "slack": {      "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",      "is_primary": true    }  }}
```

**XONG!** Slack sẽ nhận alerts tự động

---

## 7. TROUBLESHOOTING

### Lỗi Connection

```
ConnectionError: Không thể kết nối database
```

**Fix:**

-    Check database đang chạy: `systemctl status mongodb`
-    Check credentials trong `common_config.json`
-    Check firewall: `sudo ufw allow 27017`

### Lỗi Import

```
ImportError: Thiếu thư viện
```

**Fix:**

```bash
pip install -r requirements.txt
```

### Discord Webhook Failed

```
Lỗi gửi đến Discord: 404
```

**Fix:**

-    Check webhook URL đúng format
-    Test webhook: `curl -X POST webhook_url -d '{"content":"test"}'`

### Data Cũ Spam Alerts

```
Nhận quá nhiều alerts cho data cũ
```

**Fix:**Set `max_stale_days` trong config:

```json
"check": {  "max_stale_days": 3}
```

### Performance Issues

```
CPU/RAM cao
```

**Fix:**

-    Tăng `check_frequency` (giảm tần suất check)
-    Tạo index trên database:
    
    ```sql
    CREATE INDEX idx_datetime ON table(datetime);CREATE INDEX idx_symbol_datetime ON table(symbol, datetime);
    ```
    
-    Check số tasks: `ps aux | grep python`

### Symbols Không Auto-sync

```
Không lấy được symbols từ database
```

**Fix:**

-    Check `auto_sync: true` và `column` đúng
-    Check quyền đọc database
-    Xóa cache: `rm -rf cache/*`

---

## PERFORMANCE TIPS

### Database Optimization

1.  **Tạo indexes:**
    
    ```sql
    -- PostgreSQLCREATE INDEX idx_datetime ON table(datetime);CREATE INDEX idx_symbol ON table(symbol);-- MongoDBdb.collection.createIndex({datetime: -1})db.collection.createIndex({symbol: 1, datetime: -1})
    ```
    
2.  **Config optimization:**
    
    ```json
    {  "check_frequency": 60,  "alert_frequency": 300}
    ```
    

### Caching Strategy

-   **Symbols**: Cache 24h trong `cache/`
-   **Config**: Mtime-based reload
-   **Connections**: Pooling tự động
-   **Class-level**: Persist qua config reloads

### Resource Usage

Metric

Value

RAM/task

~2-5MB

CPU idle

<1%

CPU active

5-10%

Disk I/O

Minimal (cache)

---
>>>>>>> 6342fad4541a6f43092b52b6892311d378867ee1
