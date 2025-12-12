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
- **Cài packages**:

### Windows PowerShell
```powershell
git clone https://github.com/adee0210/check-data-project
cd check_data_project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux / macOS
```bash
git clone https://github.com/adee0210/check-data-project
cd check_data_project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

### Chạy trực tiếp (Development)
```powershell
.\.venv\Scripts\Activate.ps1
python src\main.py
```

### Xem logs
```powershell
Get-Content logs\main.log -Wait -Tail 100
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

---

## Ví dụ cấu hình

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

---

**Author:** adee0210  
**Repository:** [https://github.com/adee0210/check-data-project](https://github.com/adee0210/check-data-project)