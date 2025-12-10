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
Kiểm tra file/folder modification time (mtime, ctime, atime)

### ✨ Tính Năng Chính

- ⚡ **Async Architecture**: Chạy song song nhiều tasks, không block
- 🔄 **Dynamic Reload**: Tự động reload config mỗi 10s
- 💾 **Smart Caching**: Cache symbols 24h, connections pooling
- 🎯 **Optimized Queries**: PostgreSQL dùng MAX/MIN, MongoDB dùng projection
- 🏖️ **Holiday Detection**: Phát hiện ngày lễ thông minh
- 📢 **Multi-Platform Alerts**: Discord, Telegram (dễ thêm Slack, Email...)
- 🛑 **Auto Shutdown**: Dừng task khi data cũ quá ngưỡng

---

## 2. CÀI ĐẶT

### Yêu Cầu

- Python 3.7+
- MongoDB hoặc PostgreSQL (optional)

### Cài Đặt Dependencies

```bash
# Clone repository
git clone https://github.com/adee0210/check-data-project
cd check_data_project

# Tạo virtual environment
python -m venv .venv

# Kích hoạt
.venv\Scripts\Activate.ps1  # Windows PowerShell
# hoặc
source .venv/bin/activate    # Linux/Mac

# Cài packages
pip install -r requirements.txt
```

### Cấu Trúc Thư Mục

```
check_data_project/
├── configs/                            # Cấu hình
│   ├── common_config.json              # Platform + DB credentials
│   ├── data_sources_config.json        # Data sources
│   ├── check_disk_config.json          # Disk monitoring
│   ├── database_config/                # Database connectors
│   │   ├── base_db.py                  # Abstract base class
│   │   ├── mongo_config.py             # MongoDB connector
│   │   ├── postgres_config.py          # PostgreSQL connector
│   │   └── database_manager.py         # Factory manager
│   └── logging_config.py               # Logging config
│
├── src/
│   ├── main.py                         # Entry point
│   ├── check/                          # Monitors
│   │   ├── check_api.py                # API monitor
│   │   ├── check_database.py           # Database monitor
│   │   └── check_disk.py               # Disk monitor
│   ├── logic_check/                    # Business logic
│   │   ├── data_validator.py           # Data freshness validation
│   │   └── time_validator.py           # Schedule validation
│   └── utils/                          # Utilities
│       ├── platform_util/              # Platform notifiers
│       │   ├── base_platform.py        # Abstract base class
│       │   ├── discord_util.py         # Discord notifier
│       │   ├── telegram_util.py        # Telegram notifier
│       │   └── platform_manager.py     # Factory manager
│       ├── load_config_util.py         # Config loader
│       ├── symbol_resolver_util.py     # Symbol resolver
│       └── convert_datetime_util.py    # Datetime utils
│
├── cache/                              # Auto-generated cache
├── logs/                               # Log files
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

Cấu trúc hierarchical với 5 sections:

```json
{
  "source-name": {
    "api": {
      "enable": true,
      "url": "http://example.com/api?symbol={symbol}",
      "record_pointer": 0,
      "column_to_check": "datetime"
    },
    "database": {
      "enable": true,
      "type": "mongodb",
      "database": "db_name",
      "collection_name": "collection",
      "record_pointer": 0,
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
      "days": [0, 1, 2, 3, 4],
      "hours": ["9:00-11:30", "13:00-14:30"]
    }
  }
}
```

#### Giải Thích Config

**api section:**
- `enable`: Bật/tắt kiểm tra API
- `url`: API endpoint, có thể dùng `{symbol}` placeholder
- `record_pointer`: `0` = mới nhất, `-1` = cũ nhất
- `column_to_check`: Field chứa timestamp trong JSON response

**database section:**
- `enable`: Bật/tắt kiểm tra database
- `type`: `"mongodb"` hoặc `"postgresql"`
- `collection_name`: Tên collection (MongoDB)
- `table`: Tên table (PostgreSQL)
- `record_pointer`: `0` = MAX, `-1` = MIN

**symbols section:**
- `auto_sync`: `true` = tự động lấy từ DB, `false` = dùng manual list, `null` = không cần
- `values`: Array symbols nếu `auto_sync=false`
- `column`: Column chứa symbol

**check section:**
- `timezone_offset`: Offset timezone (0=UTC, 7=GMT+7)
- `allow_delay`: Độ trễ tối đa cho phép (giây)
- `check_frequency`: Tần suất check (giây)
- `alert_frequency`: Tần suất alert (giây)
- `max_stale_days`: Dừng task khi data cũ quá X ngày

**schedule section:**
- `days`: Array ngày (0=Mon, 6=Sun), `null` = all days
- `hours`: Array khung giờ, `null` = 24/7

### 3.3. Ví Dụ Cấu Hình

#### API + Database

```json
{
  "binance": {
    "api": {
      "enable": true,
      "url": "https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}",
      "record_pointer": 0,
      "column_to_check": "closeTime"
    },
    "database": {
      "enable": true,
      "type": "mongodb",
      "database": "crypto",
      "collection_name": "binance",
      "record_pointer": 0,
      "column_to_check": "timestamp"
    },
    "symbols": {
      "auto_sync": true,
      "values": null,
      "column": "symbol"
    },
    "check": {
      "timezone_offset": 0,
      "allow_delay": 120,
      "check_frequency": 30,
      "alert_frequency": 300,
      "max_stale_days": 1
    },
    "schedule": {
      "days": null,
      "hours": null
    }
  }
}
```

#### Chỉ API

```json
{
  "gold-price": {
    "api": {
      "enable": true,
      "url": "http://api.example.com/gold",
      "record_pointer": 0,
      "column_to_check": "datetime"
    },
    "database": {
      "enable": false
    },
    "symbols": {
      "auto_sync": null
    },
    "check": {
      "allow_delay": 300,
      "check_frequency": 60,
      "alert_frequency": 600,
      "max_stale_days": 3
    },
    "schedule": {
      "days": [0, 1, 2, 3, 4],
      "hours": null
    }
  }
}
```

#### Chỉ Database

```json
{
  "stock-data": {
    "api": {
      "enable": false
    },
    "database": {
      "enable": true,
      "type": "postgresql",
      "database": "stocks",
      "table": "prices",
      "record_pointer": 0,
      "column_to_check": "datetime"
    },
    "symbols": {
      "auto_sync": false,
      "values": ["VNM", "VIC", "VHM"],
      "column": "symbol"
    },
    "check": {
      "allow_delay": 3600,
      "check_frequency": 300,
      "alert_frequency": 1800,
      "max_stale_days": 7
    },
    "schedule": {
      "days": [0, 1, 2, 3, 4],
      "hours": ["9:00-11:30", "13:00-15:00"]
    }
  }
}
```

---

## 4. CHẠY HỆ THỐNG

### Development

```bash
# Chạy trực tiếp
python src/main.py
```

### Production (Windows)

```powershell
# Background
Start-Process python -ArgumentList "src/main.py" -WindowStyle Hidden
```

### Production (Linux)

```bash
# Systemd service
sudo nano /etc/systemd/system/data-monitor.service
```

```ini
[Unit]
Description=Data Monitoring System
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/check_data_project
ExecStart=/path/to/.venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable và start
sudo systemctl enable data-monitor
sudo systemctl start data-monitor
sudo systemctl status data-monitor
```

### Xem Logs

```bash
# Real-time
tail -f logs/api.log
tail -f logs/database.log
tail -f logs/disk.log

# PowerShell
Get-Content logs/api.log -Wait
```

---

## 5. KIẾN TRÚC

### 5.1. Tổng Quan

```
main.py
  ├── CheckAPI (API monitoring)
  ├── CheckDatabase (Database monitoring)
  └── CheckDisk (File monitoring)
         │
         ├── DatabaseManager (Factory pattern)
         │      ├── MongoDBConnector
         │      ├── PostgreSQLConnector
         │      └── MySQLConnector (dễ thêm)
         │
         └── PlatformManager (Factory pattern)
                ├── DiscordNotifier
                ├── TelegramNotifier
                └── SlackNotifier (dễ thêm)
```

### 5.2. Module Database Config

**Factory Pattern + Abstract Base Class**

```
BaseDatabaseConnector (ABC)
  ├── connect()
  ├── query()
  ├── close()
  └── get_required_package()

MongoDBConnector(BaseDatabaseConnector)
  ├── connect() - pymongo.MongoClient
  ├── query() - find().sort().limit() với projection
  └── close()

PostgreSQLConnector(BaseDatabaseConnector)
  ├── connect() - psycopg2.connect
  ├── query() - SELECT MAX/MIN (không dùng ORDER BY)
  └── close()

DatabaseManager (Factory)
  ├── CONNECTOR_REGISTRY = {type: class}
  ├── _create_connector() - Factory method
  ├── connect() - Connection pooling
  └── query() - Unified interface
```

**Sử dụng:**

```python
from configs.database_config import DatabaseManager

manager = DatabaseManager()
latest_time = manager.query("db_name", config, symbol="BTC")
manager.close("db_name")
```

### 5.3. Module Platform Util

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

PlatformManager (Factory)
  ├── NOTIFIER_REGISTRY = {name: class}
  ├── _create_notifier() - Factory method
  ├── send_alert() - Gửi đến TẤT CẢ primary platforms
  └── send_to_specific_platform()
```

**Sử dụng:**

```python
from utils.platform_util import PlatformManager

manager = PlatformManager()
manager.send_alert(
    api_name="BTC-API",
    symbol="BTC",
    overdue_seconds=300,
    allow_delay=120,
    check_frequency=60,
    alert_frequency=300
)
```

### 5.4. Luồng Hoạt Động

#### Check API

```
1. Load config (mỗi 10s)
2. Resolve symbols (cache 24h)
3. Tạo/hủy tasks động
4. Mỗi task:
   - Check schedule
   - GET request API
   - Parse JSON
   - Validate timestamp
   - Check max_stale_days → Exit nếu quá cũ
   - Detect holiday
   - Send alert nếu cần
   - Sleep check_frequency
```

#### Check Database

```
1. Load config (mỗi 10s)
2. Resolve symbols (cache 24h)
3. Tạo/hủy tasks động
4. Mỗi task:
   - Check schedule
   - Query database (MAX/MIN hoặc find+sort)
   - Validate timestamp
   - Check max_stale_days → Exit nếu quá cũ
   - Detect holiday
   - Send alert nếu cần
   - Sleep check_frequency
```

#### Holiday Detection

```
1. Track first_stale_times
2. Đếm số items stale
3. Check: latest_data_date == current_date?
4. Nếu NO + stale_count >= 50%:
   → Nghi ngờ ngày lễ
5. Gửi alert với emoji 🟡
```

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
