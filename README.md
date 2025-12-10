# HỆ THỐNG GIÁM SÁT DỮ LIỆU

## 📋 MỤC LỤC

1. [Tổng Quan](#1-tổng-quan)
2. [Cài Đặt](#2-cài-đặt)
3. [Cấu Hình](#3-cấu-hình)
4. [Chạy Hệ Thống](#4-chạy-hệ-thống)
5. [Kiến Trúc](#5-kiến-trúc)
6. [Mở Rộng](#6-mở-rộng)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. TỔNG QUAN

Hệ thống giám sát tự động kiểm tra tính cập nhật (freshness) của dữ liệu từ 3 nguồn:

### 🌐 API Endpoints
Kiểm tra HTTP API responses, parse JSON và so sánh timestamp

### 🗄️ Database
Hỗ trợ MongoDB và PostgreSQL, tối ưu queries với MAX/MIN và projection

### 📁 Disk Files
Đọc nội dung file (JSON, CSV, TXT) hoặc kiểm tra file modification time

### ✨ Tính Năng Chính

- ⚡ **Async Architecture**: Chạy song song nhiều tasks, không block
- 🔄 **Dynamic Reload**: Tự động reload config mỗi 10s
- 💾 **Smart Caching**: Cache symbols 24h, connections pooling
- 🎯 **Optimized Queries**: PostgreSQL dùng MAX/MIN, MongoDB dùng projection
- 🏖️ **Holiday Detection**: Phát hiện ngày lễ thông minh
- 📢 **Multi-Platform Alerts**: Discord, Telegram (dễ thêm Slack, Email...)
- 🛑 **Auto Shutdown**: Dừng task khi data cũ quá ngưỡng
- 📂 **File Content Reading**: Hỗ trợ đọc JSON, CSV, TXT để lấy datetime
- ⏰ **Flexible Scheduling**: Schedule riêng cho từng data source

---

## 2. CÀI ĐẶT

### Yêu Cầu

- Python 3.7+
- MongoDB hoặc PostgreSQL (optional, nếu dùng Database monitoring)

### Cài Đặt Dependencies

#### Linux/Mac
```bash
# Clone repository
git clone https://github.com/adee0210/check-data-project
cd check_data_project

# Tạo virtual environment
python -m venv .venv

# Kích hoạt
source .venv/bin/activate

# Cài packages
pip install -r requirements.txt
```

#### Windows
```powershell
# Clone repository
git clone https://github.com/adee0210/check-data-project
cd check_data_project

# Tạo virtual environment
python -m venv .venv

# Kích hoạt
.venv\Scripts\Activate.ps1

# Cài packages
pip install -r requirements.txt
```

### Cấu Trúc Thư Mục

```
check_data_project/
├── configs/                            # Cấu hình
│   ├── common_config.json              # Platform + DB credentials
│   ├── data_sources_config.json        # Data sources (API, DB, Disk)
│   ├── database_config/                # Database connectors
│   │   ├── base_db.py                  # Abstract base class
│   │   ├── mongo_config.py             # MongoDB connector
│   │   ├── postgres_config.py          # PostgreSQL connector
│   │   └── database_manager.py         # Factory manager
│   └── logging_config.py               # Logging config (10MB/file, 5 files)
│
├── src/
│   ├── main.py                         # Entry point
│   ├── check/                          # Monitors
│   │   ├── check_api.py                # API monitor
│   │   ├── check_database.py           # Database monitor
│   │   └── check_disk.py               # Disk/File monitor
│   ├── logic_check/                    # Business logic
│   │   ├── data_validator.py           # Data freshness validation
│   │   └── time_validator.py           # Schedule validation
│   └── utils/                          # Utilities
│       ├── platform_util/              # Platform notifiers
│       │   ├── base_platform.py        # Abstract base class
│       │   ├── discord_util.py         # Discord notifier
│       │   ├── telegram_util.py        # Telegram notifier
│       │   └── platform_manager.py     # Factory manager
│       ├── load_config_util.py         # Config loader with caching
│       ├── symbol_resolver_util.py     # Symbol resolver
│       ├── task_manager_util.py        # Task manager
│       └── convert_datetime_util.py    # Datetime utils
│
├── cache/                              # Auto-generated cache
├── logs/                               # Log files (api.log, database.log, main.log)
├── run.sh                              # Linux/Mac startup script
├── run.ps1                             # Windows startup script
└── requirements.txt
```

---

## 3. CẤU HÌNH

### 3.1. Platform Config (`common_config.json`)

```json
{
  "PLATFORM_CONFIG": {
    "discord": {
      "webhooks_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
      "is_primary": true
    },
    "telegram": {
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID",
      "is_primary": false
    }
  },
  "MONGO_CONFIG": {
    "host": "localhost",
    "port": 27017,
    "username": "admin",
    "password": "password",
    "auth_source": "admin"
  },
  "POSTGRE_CONFIG": {
    "host": "localhost",
    "port": 5432,
    "database": "your_db",
    "user": "postgres",
    "password": "password"
  }
}
```

### 3.2. Data Sources Config (`data_sources_config.json`)

**Cấu trúc thống nhất cho tất cả data sources:**

```json
{
  "source-name": {
    "api": {
      "enable": true,
      "url": "https://api.example.com/data?symbol={symbol}",
      "record_pointer": "first",
      "column_to_check": "datetime"
    },
    "database": {
      "enable": true,
      "type": "mongodb",
      "database": "db_name",
      "collection_name": "collection",
      "record_pointer": "first",
      "column_to_check": "datetime"
    },
    "disk": {
      "enable": true,
      "file_type": "json",
      "file_path": "/path/to/file.json",
      "record_pointer": "first",
      "column_to_check": "datetime"
    },
    "symbols": {
      "auto_sync": true,
      "values": null,
      "column": "symbol"
    },
    "check": {
      "timezone_offset": 7,
      "allow_delay": 60,
      "check_frequency": 10,
      "alert_frequency": 60,
      "max_stale_days": 3
    },
    "schedule": {
      "valid_days": [0, 1, 2, 3, 4],
      "time_ranges": ["09:00-11:30", "13:00-14:30"]
    }
  }
}
```

#### Giải Thích Config

**api section:**
- `enable`: Bật/tắt kiểm tra API
- `url`: API endpoint, có thể dùng `{symbol}` placeholder
- `record_pointer`: `"first"` = record đầu tiên, `"last"` = record cuối cùng
- `column_to_check`: Field chứa timestamp trong JSON response

**database section:**
- `enable`: Bật/tắt kiểm tra database
- `type`: `"mongodb"` hoặc `"postgresql"`
- `collection_name`: Tên collection (MongoDB)
- `table`: Tên table (PostgreSQL)
- `record_pointer`: `"first"` = MIN value, `"last"` = MAX value
- `column_to_check`: Column chứa timestamp

**disk section:** *(NEW)*
- `enable`: Bật/tắt kiểm tra file trên disk
- `file_type`: `"json"`, `"csv"`, `"txt"`, hoặc `"mtime"` (modification time)
- `file_path`: Đường dẫn đầy đủ đến file (có thể dùng `{symbol}` placeholder)
- `record_pointer`: `"first"` = record đầu tiên, `"last"` = record cuối cùng
- `column_to_check`: Column/key chứa timestamp (bỏ qua nếu `file_type="mtime"`)

**symbols section:**
- `auto_sync`: `true` = tự động lấy từ DB, `false` = dùng manual list, `null` = không cần
- `values`: Array symbols nếu `auto_sync=false`
- `column`: Column chứa symbol

**check section:**
- `timezone_offset`: Offset timezone (0=UTC, 7=GMT+7)
- `allow_delay`: Độ trễ tối đa cho phép (giây)
- `check_frequency`: Tần suất check (giây)
- `alert_frequency`: Tần suất alert (giây) - tránh spam
- `max_stale_days`: Dừng task khi data cũ quá X ngày (smart holiday detection)

**schedule section:**
- `valid_days`: Array ngày (0=Mon, 6=Sun), `null` = all days
- `time_ranges`: Array khung giờ HH:MM-HH:MM, `null` = 24/7

### 3.3. Ví Dụ Cấu Hình

#### 1. API + Database

```json
{
  "binance": {
    "api": {
      "enable": true,
      "url": "https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}",
      "record_pointer": "last",
      "column_to_check": "closeTime"
    },
    "database": {
      "enable": true,
      "type": "mongodb",
      "database": "crypto",
      "collection_name": "binance",
      "record_pointer": "last",
      "column_to_check": "timestamp"
    },
    "symbols": {
      "auto_sync": true,
      "values": null,
      "column": "symbol"
    },
    "check": {
      "timezone_offset": 0,
      "allow_delay": 300,
      "check_frequency": 30,
      "alert_frequency": 300,
      "max_stale_days": 2
    },
    "schedule": {
      "valid_days": null,
      "time_ranges": null
    }
  }
}
```

#### 2. Disk JSON File (Multi-Symbol)

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
      "max_stale_days": 1
    },
    "schedule": {
      "valid_days": [0, 1, 2, 3, 4],
      "time_ranges": ["09:00-11:30", "13:00-15:00"]
    }
  }
}
```

#### 3. Disk CSV File (Single File)

```json
{
  "daily-report": {
    "disk": {
      "enable": true,
      "file_type": "csv",
      "file_path": "/reports/daily_report.csv",
      "record_pointer": "last",
      "column_to_check": "report_date"
    },
    "symbols": {
      "auto_sync": null,
      "values": null,
      "column": null
    },
    "check": {
      "timezone_offset": 7,
      "allow_delay": 3600,
      "check_frequency": 300,
      "alert_frequency": 1800,
      "max_stale_days": 1
    },
    "schedule": {
      "valid_days": [0, 1, 2, 3, 4],
      "time_ranges": ["17:00-23:59"]
    }
  }
}
```

#### 4. Disk Text File (First Line Check)

```json
{
  "log-monitor": {
    "disk": {
      "enable": true,
      "file_type": "txt",
      "file_path": "/logs/app.log",
      "record_pointer": "first",
      "column_to_check": null
    },
    "symbols": {
      "auto_sync": null,
      "values": null,
      "column": null
    },
    "check": {
      "timezone_offset": 7,
      "allow_delay": 120,
      "check_frequency": 10,
      "alert_frequency": 60,
      "max_stale_days": 1
    },
    "schedule": {
      "valid_days": null,
      "time_ranges": null
    }
  }
}
```

#### 5. Disk File Modification Time

```json
{
  "backup-check": {
    "disk": {
      "enable": true,
      "file_type": "mtime",
      "file_path": "/backups/db_backup_{symbol}.sql",
      "record_pointer": null,
      "column_to_check": null
    },
    "symbols": {
      "auto_sync": false,
      "values": ["prod", "staging", "dev"],
      "column": null
    },
    "check": {
      "timezone_offset": 7,
      "allow_delay": 7200,
      "check_frequency": 600,
      "alert_frequency": 3600,
      "max_stale_days": 1
    },
    "schedule": {
      "valid_days": null,
      "time_ranges": ["08:00-20:00"]
    }
  }
}
```

#### 6. Mixed: API + Database + Disk

```json
{
  "full-stack": {
    "api": {
      "enable": true,
      "url": "https://api.example.com/data?id={symbol}",
      "record_pointer": "last",
      "column_to_check": "timestamp"
    },
    "database": {
      "enable": true,
      "type": "postgresql",
      "database": "production",
      "table": "events",
      "record_pointer": "last",
      "column_to_check": "created_at"
    },
    "disk": {
      "enable": true,
      "file_type": "json",
      "file_path": "/cache/{symbol}_cache.json",
      "record_pointer": "last",
      "column_to_check": "cached_at"
    },
    "symbols": {
      "auto_sync": true,
      "values": null,
      "column": "event_id"
    },
    "check": {
      "timezone_offset": 7,
      "allow_delay": 180,
      "check_frequency": 30,
      "alert_frequency": 300,
      "max_stale_days": 2
    },
    "schedule": {
      "valid_days": [0, 1, 2, 3, 4],
      "time_ranges": ["08:00-12:00", "13:00-17:00"]
    }
  }
}
}
```

---

## 4. CHẠY HỆ THỐNG

### Linux/Mac (run.sh)

#### Khởi động
```bash
./run.sh start
```

#### Kiểm tra trạng thái
```bash
./run.sh status
```

#### Xem logs (Interactive Menu)
```bash
./run.sh logs
# Chọn:
# 1) main.log
# 2) api.log
# 3) database.log
# 4) disk.log
```

#### Dừng
```bash
./run.sh stop
```

### Windows (run.ps1)

#### Khởi động (Background)
```powershell
.\run.ps1 start
```

#### Kiểm tra trạng thái
```powershell
.\run.ps1 status
```

#### Xem logs (Interactive Menu)
```powershell
.\run.ps1 logs
# Chọn:
# 1) main.log
# 2) api.log
# 3) database.log
# 4) disk.log
```

#### Dừng
```powershell
.\run.ps1 stop
```

### Chạy trực tiếp Python (Development)

```bash
# Linux/Mac
source .venv/bin/activate
python src/main.py

# Windows
.venv\Scripts\activate
python src\main.py

### Development

```bash
# Chạy trực tiếp
python src/main.py
```

### Production (Windows)

```

### Xem Logs

#### Linux/Mac
```bash
# Real-time
tail -f logs/api.log
tail -f logs/database.log
tail -f logs/disk.log
tail -f logs/main.log
```

#### Windows PowerShell
```powershell
Get-Content logs\api.log -Wait -Tail 50
Get-Content logs\database.log -Wait -Tail 50
Get-Content logs\disk.log -Wait -Tail 50
```

---

## 5. KIẾN TRÚC

### 5.1. Tổng Quan

```
main.py (async orchestrator)
  │
  ├── CheckAPI (API monitoring)
  │     └── aiohttp sessions
  │
  ├── CheckDatabase (Database monitoring)
  │     └── DatabaseManager → MongoDB/PostgreSQL
  │
  └── CheckDisk (Disk/File monitoring)
        └── File readers: JSON/CSV/TXT/mtime
              │
              ├── DataValidator (freshness check logic)
              ├── TimeValidator (schedule validation)
              │
              ├── DatabaseManager (Factory pattern)
              │      ├── MongoDBConnector
              │      ├── PostgreSQLConnector
              │      └── MySQLConnector (extensible)
              │
              └── PlatformManager (Factory pattern)
                     ├── DiscordNotifier
                     ├── TelegramNotifier
                     └── SlackNotifier (extensible)
```

### 5.2. Data Flow

```
┌─────────────────┐
│  Config Loader  │  (auto-reload every 10s)
└────────┬────────┘
         │
         ├────────────────┬────────────────┬──────────────────┐
         ▼                ▼                ▼                  ▼
   ┌─────────┐      ┌──────────┐     ┌──────────┐     ┌──────────┐
   │ CheckAPI│      │CheckDB   │     │CheckDisk │     │TimeValid │
   └────┬────┘      └─────┬────┘     └─────┬────┘     └─────┬────┘
        │                 │                │                │
        │ HTTP GET        │ SQL Query      │ File Read      │ Schedule?
        ▼                 ▼                ▼                ▼
   ┌─────────────────────────────────────────────────────────┐
   │              DataValidator                               │
   │  ├─ Parse datetime                                       │
   │  ├─ Calculate delay                                      │
   │  ├─ Check stale_count                                    │
   │  └─ Holiday detection                                    │
   └──────────────────────┬──────────────────────────────────┘
                          │ is_stale?
                          ▼
                   ┌──────────────┐
                   │PlatformMgr   │
                   │send_alert()  │
                   └──────┬───────┘
                          │
                   ┌──────┴───────┐
                   ▼              ▼
            ┌──────────┐   ┌───────────┐
            │ Discord  │   │ Telegram  │
            └──────────┘   └───────────┘
```

### 5.3. Database Manager (Factory Pattern)

**Abstract Base Class:**

```python
class BaseDatabaseConnector(ABC):
    @abstractmethod
    def connect(self): pass
    
    @abstractmethod
    def query(self, config, symbol=None): pass
    
    @abstractmethod
    def close(self): pass
    
    @abstractmethod
    def get_required_package(self) -> str: pass
```

**Concrete Implementations:**

```python
MongoDBConnector(BaseDatabaseConnector)
  ├── connect() → pymongo.MongoClient
  ├── query() → collection.find().sort().limit(1)
  │            with projection for optimization
  └── close() → client.close()

PostgreSQLConnector(BaseDatabaseConnector)
  ├── connect() → psycopg2.connect
  ├── query() → SELECT MAX(col) / MIN(col)
  │            (no ORDER BY for performance)
  └── close() → connection.close()
```

**Factory:**

```python
class DatabaseManager:
    CONNECTOR_REGISTRY = {
        "mongodb": MongoDBConnector,
        "postgresql": PostgreSQLConnector
    }
    
    def _create_connector(self, db_type):
        return self.CONNECTOR_REGISTRY[db_type](config)
    
    def query(self, db_name, config, symbol=None):
        # Connection pooling + unified interface
        connector = self._get_or_create(db_name, config)
        return connector.query(config, symbol)
```

### 5.4. Platform Manager (Factory Pattern)

**Factory Pattern + Multi-Platform Support**

```
BasePlatformNotifier (ABC)
  ├── send_alert()
  ├── validate_config()
  ├── get_platform_name()
  └── format_time()

DiscordNotifier(BasePlatformNotifier)
  ├── send_alert() - Webhook với rich embed
  └── validate_config()

TelegramNotifier(BasePlatformNotifier)
  ├── send_alert() - Bot API với Markdown
  └── validate_config()

**Abstract Base Class:**

```python
class BasePlatform(ABC):
    @abstractmethod
    def send_message(self, message: str) -> bool: pass
    
    @abstractmethod
    def format_alert(self, **kwargs) -> str: pass
```

**Concrete Implementations:**

```python
DiscordNotifier(BasePlatform)
  ├── send_message() → webhook POST
  └── format_alert() → Discord embed format

TelegramNotifier(BasePlatform)
  ├── send_message() → Bot API sendMessage
  └── format_alert() → Markdown format
```

**Factory:**

```python
class PlatformManager:
    NOTIFIER_REGISTRY = {
        "discord": DiscordNotifier,
        "telegram": TelegramNotifier
    }
    
    def send_alert(self, api_name, symbol, overdue_seconds, 
                   allow_delay, check_frequency, alert_frequency):
        # Send to ALL primary platforms
        for platform in self.notifiers.values():
            if platform.is_primary:
                platform.send_message(message)
```

### 5.5. Disk File Reading Logic

```python
def _read_datetime_from_file(self, file_path, file_type, 
                              record_pointer, column_to_check):
    if file_type == "mtime":
        # File modification time
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime)
    
    elif file_type == "json":
        with open(file_path, 'r') as f:
            data = json.load(f)
            # data can be dict or list
            if isinstance(data, list):
                record = data[0 if record_pointer == "first" else -1]
            else:
                record = data
            return parse_datetime(record[column_to_check])
    
    elif file_type == "csv":
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            record = rows[0 if record_pointer == "first" else -1]
            return parse_datetime(record[column_to_check])
    
    elif file_type == "txt":
        with open(file_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            line = lines[0 if record_pointer == "first" else -1]
            return parse_datetime(line)
```

### 5.6. Flow Diagram

#### Check API Flow

```
1. Load config (auto-reload every 10s)
2. Resolve symbols (cached 24h)
3. Create/destroy tasks dynamically
4. Each task loop:
   ├─ TimeValidator.is_within_schedule()?
   │   └─ No → sleep check_frequency → continue
   ├─ HTTP GET {url}
   ├─ Parse JSON → extract datetime
   ├─ DataValidator.is_stale()?
   │   ├─ stale_count > max_stale_days?
   │   │   └─ Yes → logger.info + break (exit task)
   │   ├─ Holiday detection (pattern analysis)
   │   └─ should_send_alert()?
   │        └─ Yes → PlatformManager.send_alert()
   └─ sleep(check_frequency)
```

#### Check Database Flow

```
1. Load config (auto-reload every 10s)
2. Resolve symbols (cached 24h)
3. DatabaseManager.connect() → pooling
4. Each task loop:
   ├─ TimeValidator.is_within_schedule()?
   ├─ DatabaseManager.query()
   │   ├─ MongoDB: find().sort().limit(1) with projection
   │   └─ PostgreSQL: SELECT MAX/MIN (optimized)
   ├─ DataValidator.is_stale()?
   │   ├─ stale_count check
   │   ├─ Holiday detection
   │   └─ Alert throttling (alert_frequency)
   └─ sleep(check_frequency)
```

#### Check Disk Flow

```
1. Load config (auto-reload every 10s)
2. Resolve symbols OR single file
3. Each task loop:
   ├─ TimeValidator.is_within_schedule()?
   ├─ _read_datetime_from_file()
   │   ├─ mtime: os.path.getmtime()
   │   ├─ json: json.load() → first/last record
   │   ├─ csv: csv.DictReader() → first/last row
   │   └─ txt: readlines() → first/last line
   ├─ Parse datetime string
   ├─ DataValidator.is_stale()?
   │   ├─ stale_count check
   │   ├─ Holiday detection
   │   └─ Alert throttling
   └─ sleep(check_frequency)
```

---

## 6. MỞ RỘNG

### 6.1. Thêm Database Mới (MySQL)

**Bước 1:** Tạo connector class

```python
# configs/database_config.py
class MySQLConnector(BaseDatabaseConnector):
    def connect(self):
        import mysql.connector
        return mysql.connector.connect(**self.config)
    
    def query(self, config, symbol=None):
        # Similar to PostgreSQL logic
        pass
    
    def get_required_package(self) -> str:
        return "mysql-connector-python"
```

**Bước 2:** Đăng ký vào registry

```python
class DatabaseManager:
    CONNECTOR_REGISTRY = {
        "mongodb": MongoDBConnector,
        "postgresql": PostgreSQLConnector,
        "mysql": MySQLConnector  # Add this
    }
```

**Bước 3:** Cập nhật config

```json
{
  "database": {
    "enable": true,
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "database": "mydb"
  }
}
```

### 6.2. Thêm Platform Mới (Slack)

**Bước 1:** Tạo notifier class

```python
# utils/platform_util/slack_util.py
from .base_platform import BasePlatform

class SlackNotifier(BasePlatform):
    def __init__(self, webhook_url, is_primary=False):
        super().__init__(is_primary)
        self.webhook_url = webhook_url
    
    def send_message(self, message: str) -> bool:
        payload = {"text": message}
        response = requests.post(self.webhook_url, json=payload)
        return response.status_code == 200
    
    def format_alert(self, api_name, symbol, overdue_seconds, 
                     allow_delay, **kwargs):
        return f":warning: *{api_name}* - {symbol} is {overdue_seconds}s late"
```

**Bước 2:** Đăng ký vào registry

```python
# utils/platform_util/platform_manager.py
from .slack_util import SlackNotifier

class PlatformManager:
    NOTIFIER_REGISTRY = {
        "discord": DiscordNotifier,
        "telegram": TelegramNotifier,
        "slack": SlackNotifier  # Add this
    }
```

**Bước 3:** Cập nhật config

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

### 6.3. Thêm File Format Mới (XML)

Trong `src/check_disk/check_disk.py`, thêm logic vào `_read_datetime_from_file()`:

```python
def _read_datetime_from_file(self, ...):
    # ... existing code ...
    
    elif file_type == "xml":
        import xml.etree.ElementTree as ET
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Assuming XML structure: <root><record><datetime>...</datetime></record></root>
        records = root.findall('.//record')
        record = records[0 if record_pointer == "first" else -1]
        datetime_str = record.find(column_to_check).text
        return ConvertDatetimeUtil.convert_to_timezone(datetime_str, 0)
```

---

## 7. TROUBLESHOOTING

### Lỗi: "No module named 'pymongo'"

**Nguyên nhân:** Thiếu package database

**Giải pháp:**
```bash
pip install pymongo  # MongoDB
pip install psycopg2-binary  # PostgreSQL
```

### Lỗi: "Connection refused"

**Nguyên nhân:** Database không chạy hoặc sai config

**Giải pháp:**
```bash
# Check MongoDB
sudo systemctl status mongodb

# Check PostgreSQL
sudo systemctl status postgresql

# Test connection
mongo --host localhost --port 27017
psql -h localhost -U postgres
```

### Alert không gửi

**Kiểm tra:**
1. Check logs: `tail -f logs/main.log`
2. Test webhook:
   ```bash
   curl -X POST "YOUR_DISCORD_WEBHOOK" \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'
   ```
3. Check `alert_frequency` - có thể đang bị throttle
4. Check `schedule` - có thể ngoài giờ hoạt động

### Data cũ nhưng không alert

**Kiểm tra:**
1. `allow_delay`: Có thể set quá cao
2. `max_stale_days`: Task có thể đã tự dừng
3. Logs: Xem có "Holiday suspected" không
4. Timezone: Check `timezone_offset` đúng chưa

### Task tự dừng

**Nguyên nhân:** Data cũ quá `max_stale_days`

**Log sẽ có:**
```
[INFO] BTC: Data has been stale for 4 days (max: 3). Stopping task.
```

**Giải pháp:**
- Tăng `max_stale_days`
- Hoặc fix data source
- Restart: `./run.sh restart`

### Windows: run.ps1 báo lỗi encoding

**Giải pháp:**
```powershell
# Set UTF-8 encoding
chcp 65001

# Hoặc trong script
$OutputEncoding = [System.Text.Encoding]::UTF8
```

### Linux: Permission denied

**Giải pháp:**
```bash
chmod +x run.sh
chmod +x src/main.py
```

---

## 8. LOGGING

### Log Files

```
logs/
├── main.log       # Orchestrator logs
├── api.log        # API check logs
├── database.log   # Database check logs
└── disk.log       # Disk check logs
```

### Log Rotation

- **maxBytes:** 10MB per file
- **backupCount:** 4 (total 5 files)
- **Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

### Log Levels

- **INFO:** Normal operations
- **WARNING:** Stale data, holidays
- **ERROR:** Connection failures, exceptions
- **DEBUG:** Detailed troubleshooting (enable in `logging_config.py`)

---

## 9. BEST PRACTICES

### Config Management

✅ **DO:**
- Separate configs by environment (dev/prod)
- Use environment variables for sensitive data
- Enable only needed monitors (`enable: false` for unused)
- Set reasonable `check_frequency` (avoid DDoS)

❌ **DON'T:**
- Commit secrets to git
- Set `check_frequency` < 5s
- Use same webhook for dev/prod

### Performance Optimization

✅ **DO:**
- Enable `auto_sync: true` for symbol caching
- Use `record_pointer: "last"` for latest data
- Set appropriate `alert_frequency` (avoid spam)
- Use projection in MongoDB queries

❌ **DON'T:**
- Query full collections without limits
- Set `max_stale_days` too low
- Run too many concurrent tasks

### Alert Management

✅ **DO:**
- Set `is_primary: true` for main platform
- Use `alert_frequency` >= 60s
- Test webhooks before production
- Monitor logs regularly

❌ **DON'T:**
- Send alerts to public channels
- Ignore "Holiday suspected" warnings
- Set `allow_delay` too low

---

## 10. FAQ

**Q: Có thể monitor nhiều nguồn trong 1 config?**

A: Có! Set `enable: true` cho api, database, disk cùng lúc.

**Q: Schedule hoạt động thế nào?**

A: `valid_days` (0=Mon, 6=Sun), `time_ranges` (HH:MM-HH:MM). `null` = always on.

**Q: Làm sao biết data cũ do lỗi hay do ngày lễ?**

A: Xem emoji:
- 🔴 Data stale (error)
- 🟡 Holiday suspected (warning)

**Q: alert_frequency khác check_frequency thế nào?**

A:
- `check_frequency`: Tần suất CHECK data
- `alert_frequency`: Tần suất GỬI alert (tránh spam)

**Q: File type "txt" đọc thế nào?**

A: Đọc dòng đầu/cuối, parse thành datetime. Format phải là ISO8601 hoặc timestamp.

**Q: record_pointer "first" vs "last"?**

A:
- `"first"`: Record đầu tiên (oldest)
- `"last"`: Record cuối cùng (latest)

**Q: Có thể dùng placeholder {symbol} ở đâu?**

A: `api.url`, `disk.file_path`

---

## 11. LICENSE

MIT License

---

## 12. CREDITS

**Author:** adee0210

**Contributors:** Welcome! PRs appreciated.

**Repository:** https://github.com/adee0210/check-data-project

---

## 6. MỞ RỘNG

### 6.1. Thêm Database Mới (MySQL)

#### Bước 1: Tạo Connector

Tạo file `configs/database_config/mysql_config.py`:

```python
"""MySQL Connector"""
from typing import Any, Dict, Optional
from datetime import datetime
from .base_db import BaseDatabaseConnector

class MySQLConnector(BaseDatabaseConnector):
    """MySQL connector implementation"""
    
    def __init__(self, logger):
        super().__init__(logger)
    
    def connect(self, config: Dict[str, Any]) -> Any:
        """Kết nối MySQL"""
        try:
            import mysql.connector
        except ImportError:
            raise ImportError(
                f"Thiếu thư viện MySQL. "
                f"Cài đặt: pip install {self.get_required_package()}"
            )
        
        self.validate_config(config, ["host", "database", "username", "password"])
        
        self.connection = mysql.connector.connect(
            host=config["host"],
            port=config.get("port", 3306),
            database=config["database"],
            user=config["username"],
            password=config["password"]
        )
        
        self.logger.info(f"Kết nối MySQL thành công: {config['database']}")
        return self.connection
    
    def query(self, config: Dict[str, Any], symbol: Optional[str] = None) -> datetime:
        """Query MySQL"""
        if not self.is_connected():
            raise ConnectionError("Chưa kết nối MySQL")
        
        self.validate_config(config, ["table", "column_to_check"])
        
        table = config["table"]
        column = config["column_to_check"]
        record_pointer = config.get("record_pointer", 0)
        symbol_column = config.get("symbol_column")
        
        agg_func = "MAX" if record_pointer == 0 else "MIN"
        query = f"SELECT {agg_func}({column}) FROM {table}"
        params = []
        
        if symbol and symbol_column:
            query += f" WHERE {symbol_column} = %s"
            params.append(symbol)
        
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        cursor.close()
        
        if result and result[0]:
            return result[0]
        raise ValueError("Không có kết quả")
    
    def close(self) -> None:
        """Đóng connection"""
        if self.connection:
            self.connection.close()
            self.logger.info("Đã đóng MySQL")
        self.connection = None
    
    def get_required_package(self) -> str:
        return "mysql-connector-python"
```

#### Bước 2: Register

Edit `configs/database_config/database_manager.py`:

```python
# Thêm import
from .mysql_config import MySQLConnector

class DatabaseManager:
    CONNECTOR_REGISTRY = {
        "mongodb": MongoDBConnector,
        "postgresql": PostgreSQLConnector,
        "mysql": MySQLConnector,  # ← THÊM
    }
    
    def _get_connection_config(self, db_type, db_config):
        # ... existing code ...
        
        elif db_type == "mysql":  # ← THÊM
            mysql_config = common_config["MYSQL_CONFIG"]
            return {
                "host": mysql_config["host"],
                "port": mysql_config["port"],
                "database": database_name or mysql_config["database"],
                "username": mysql_config["user"],
                "password": mysql_config["password"],
            }
```

#### Bước 3: Config

Edit `configs/common_config.json`:

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

**XONG!** Sử dụng: `"type": "mysql"` trong config

### 6.2. Thêm Platform Mới (Slack)

#### Bước 1: Tạo Notifier

Tạo file `src/utils/platform_util/slack_util.py`:

```python
"""Slack Notifier"""
import requests
from typing import Dict, Any, Optional
from .base_platform import BasePlatformNotifier

class SlackNotifier(BasePlatformNotifier):
    """Slack notifier implementation"""
    
    def validate_config(self) -> None:
        """Validate Slack config"""
        if not self.config.get("webhook_url"):
            raise ValueError("Thiếu 'webhook_url'")
    
    def get_platform_name(self) -> str:
        return "Slack"
    
    def send_alert(
        self,
        api_name: str,
        symbol: Optional[str],
        overdue_seconds: int,
        allow_delay: int,
        check_frequency: int,
        alert_frequency: int,
        alert_level: str = "warning",
        error_message: str = "Không có dữ liệu mới",
        error_type: Optional[str] = None,
    ) -> bool:
        """Gửi alert đến Slack"""
        if not self.is_enabled():
            return False
        
        webhook_url = self.config["webhook_url"]
        data = self.build_base_message_data(
            api_name, symbol, overdue_seconds, allow_delay,
            check_frequency, alert_frequency, alert_level,
            error_message, error_type
        )
        
        message = self._format_slack_message(data)
        
        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            if response.status_code == 200:
                self.logger.info("Gửi Slack thành công")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Lỗi gửi Slack: {e}")
            return False
    
    def _format_slack_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format Slack blocks"""
        fields = [
            {"type": "mrkdwn", "text": f"*Thời gian:*\n{data['current_time']}"},
            {"type": "mrkdwn", "text": f"*Dữ liệu cũ:*\n{data['total_time_formatted']}"},
        ]
        
        if data['symbol']:
            fields.insert(1, {"type": "mrkdwn", "text": f"*Symbol:*\n{data['symbol']}"})
        
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{data['emoji']} {data['api_name']} - {data['alert_type']}"
                    }
                },
                {"type": "section", "fields": fields}
            ]
        }
```

#### Bước 2: Register

Edit `src/utils/platform_util/platform_manager.py`:

```python
# Thêm import
from .slack_util import SlackNotifier

class PlatformManager:
    NOTIFIER_REGISTRY = {
        "discord": DiscordNotifier,
        "telegram": TelegramNotifier,
        "slack": SlackNotifier,  # ← THÊM
    }
```

#### Bước 3: Config

Edit `configs/common_config.json`:

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

**XONG!** Slack sẽ nhận alerts tự động

---

## 7. TROUBLESHOOTING

### Lỗi Connection

```
ConnectionError: Không thể kết nối database
```

**Fix:**
- ✅ Check database đang chạy: `systemctl status mongodb`
- ✅ Check credentials trong `common_config.json`
- ✅ Check firewall: `sudo ufw allow 27017`

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
- ✅ Check webhook URL đúng format
- ✅ Test webhook: `curl -X POST webhook_url -d '{"content":"test"}'`

### Data Cũ Spam Alerts

```
Nhận quá nhiều alerts cho data cũ
```

**Fix:**
Set `max_stale_days` trong config:
```json
"check": {
  "max_stale_days": 3
}
```

### Performance Issues

```
CPU/RAM cao
```

**Fix:**
- ✅ Tăng `check_frequency` (giảm tần suất check)
- ✅ Tạo index trên database:
  ```sql
  CREATE INDEX idx_datetime ON table(datetime);
  CREATE INDEX idx_symbol_datetime ON table(symbol, datetime);
  ```
- ✅ Check số tasks: `ps aux | grep python`

### Symbols Không Auto-sync

```
Không lấy được symbols từ database
```

**Fix:**
- ✅ Check `auto_sync: true` và `column` đúng
- ✅ Check quyền đọc database
- ✅ Xóa cache: `rm -rf cache/*`

---

## 📊 PERFORMANCE TIPS

### Database Optimization

1. **Tạo indexes:**
   ```sql
   -- PostgreSQL
   CREATE INDEX idx_datetime ON table(datetime);
   CREATE INDEX idx_symbol ON table(symbol);
   
   -- MongoDB
   db.collection.createIndex({datetime: -1})
   db.collection.createIndex({symbol: 1, datetime: -1})
   ```

2. **Config optimization:**
   ```json
   {
     "check_frequency": 60,
     "alert_frequency": 300
   }
   ```

### Caching Strategy

- **Symbols**: Cache 24h trong `cache/`
- **Config**: Mtime-based reload
- **Connections**: Pooling tự động
- **Class-level**: Persist qua config reloads

### Resource Usage

| Metric     | Value           |
| ---------- | --------------- |
| RAM/task   | ~2-5MB          |
| CPU idle   | <1%             |
| CPU active | 5-10%           |
| Disk I/O   | Minimal (cache) |

---

## 📞 HỖ TRỢ

**Repository:** https://github.com/adee0210/check-data-project

**Issues:** GitHub Issues

**Version:** 3.0.0 (Modular Architecture)

**Last Updated:** 2025-12-10

---

## 📝 CHANGELOG

### v3.0.0 (2025-12-10)
- ✅ Tái cấu trúc module hóa (Factory Pattern + ABC)
- ✅ Database config: Tách thành base_db, mongo, postgres, manager
- ✅ Platform util: Tách thành base_platform, discord, telegram, manager
- ✅ Dễ mở rộng: Thêm MySQL/Slack chỉ 3 bước
- ✅ Chuyển tất cả logs/comments sang tiếng Việt

### v2.0.0 (2025-12-04)
- ✅ Config restructure: Hierarchical format
- ✅ Symbols caching 24h
- ✅ Query optimization (MAX/MIN, projection)
- ✅ Holiday detection improvement
- ✅ max_stale_days auto shutdown

### v1.0.0 (2025-12-01)
- Initial release
