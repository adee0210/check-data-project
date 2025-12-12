# Alert Tracking Refactoring Summary

## Hoàn thành

### 1. AlertTracker Utility (`src/utils/alert_tracker_util.py`)
Tạo class utility để quản lý tất cả tracking logic:

**Chức năng:**
- `should_send_alert()` - Kiểm tra alert frequency
- `record_alert_sent()` - Ghi nhận đã gửi alert
- `is_in_silent_mode()` - Kiểm tra silent mode (vượt max_stale)
- `is_low_activity()` - Kiểm tra low-activity symbol
- `track_empty_data()` - Track empty data warnings với auto-silent sau 30 phút
- `reset_empty_data()` - Reset khi có data trở lại
- `track_stale_data()` - Track stale data và xác định vượt max_stale
- `track_consecutive_stale_days()` - Track ngày liên tiếp stale để detect low-activity
- `reset_fresh_data()` - Reset tất cả tracking khi data fresh
- `check_holiday_pattern()` - Phát hiện pattern ngày lễ
- `get_stale_count()` - Lấy số lượng items stale

**Tracking quản lý:**
- `last_alert_times` - Lần alert cuối
- `first_stale_times` - Lần đầu stale
- `suspected_holidays` - Ngày lễ nghi ngờ
- `outside_schedule_logged` - Log outside schedule
- `max_stale_exceeded` - Vượt max_stale (silent mode)
- `low_activity_symbols` - Low-activity symbols
- `consecutive_stale_days` - Ngày liên tiếp stale
- `empty_data_tracking` - Empty data warnings
- `last_holiday_alert_date` - Ngày gửi alert holiday cuối

### 2. CheckAPI Refactored (`src/check/check_api.py`)
✅ **Hoàn toàn refactor** để sử dụng AlertTracker:

**Thay đổi:**
- Sử dụng `self.tracker = AlertTracker()` thay vì các dict riêng lẻ
- Empty data tracking với auto-silent mode (30 phút)
- Tất cả các check alert frequency dùng `tracker.should_send_alert()`
- Tất cả ghi nhận alert dùng `tracker.record_alert_sent()`
- Reset fresh data dùng `tracker.reset_fresh_data()`
- Track stale data dùng `tracker.track_stale_data()`
- Track consecutive stale days dùng `tracker.track_consecutive_stale_days()`
- Check holiday pattern dùng `tracker.check_holiday_pattern()`

### 3. CheckDatabase (`src/check/check_database.py`)
✅ **Init refactored** - đã thay thế các dict riêng bằng `self.tracker = AlertTracker()`

⚠️ **Cần hoàn thiện** - các method sử dụng tracking vẫn dùng old style (self.last_alert_times, etc.)

### 4. CheckDisk (`src/check/check_disk.py`)
✅ **Init refactored** - đã thay thế các dict riêng bằng `self.tracker = AlertTracker()`

⚠️ **Cần hoàn thiện** - các method sử dụng tracking vẫn dùng old style (self.last_alert_times, etc.)

## Cần làm tiếp

### CheckDatabase & CheckDisk - Patterns cần thay đổi:

1. **Outside schedule logging:**
```python
# Old
if not self.outside_schedule_logged.get(display_name, False):
    ...
    self.outside_schedule_logged[display_name] = True

# New
if not self.tracker.outside_schedule_logged.get(display_name, False):
    ...
    self.tracker.outside_schedule_logged[display_name] = True
```

2. **Alert frequency check:**
```python
# Old
last_alert = self.last_alert_times.get(display_name)
should_send_alert = False
if last_alert is None:
    should_send_alert = True
else:
    time_since_last_alert = (current_time - last_alert).total_seconds()
    if time_since_last_alert >= alert_frequency:
        should_send_alert = True

# New
should_send_alert = self.tracker.should_send_alert(display_name, alert_frequency)
```

3. **Record alert sent:**
```python
# Old
self.last_alert_times[display_name] = current_time

# New
self.tracker.record_alert_sent(display_name)
```

4. **Silent mode check:**
```python
# Old
if display_name in self.max_stale_exceeded:
    ...

# New
if self.tracker.is_in_silent_mode(display_name):
    ...
```

5. **Low-activity check:**
```python
# Old
if display_name in self.low_activity_symbols:
    ...

# New
if self.tracker.is_low_activity(display_name):
    ...
```

6. **Reset fresh data:**
```python
# Old
if display_name in self.max_stale_exceeded:
    del self.max_stale_exceeded[display_name]
if display_name in self.last_alert_times:
    del self.last_alert_times[display_name]
if display_name in self.first_stale_times:
    del self.first_stale_times[display_name]
if display_name in self.consecutive_stale_days:
    del self.consecutive_stale_days[display_name]

# New
self.tracker.reset_fresh_data(display_name)
```

7. **Track stale data:**
```python
# Old
if display_name not in self.first_stale_times:
    self.first_stale_times[display_name] = current_time

total_stale_seconds = overdue_seconds + allow_delay
exceeds_max_stale = (
    max_stale_seconds is not None
    and total_stale_seconds > max_stale_seconds
)

if exceeds_max_stale:
    if display_name not in self.max_stale_exceeded:
        self.max_stale_exceeded[display_name] = current_time
        # gửi final alert
    else:
        # silent mode

# New
total_stale_seconds = overdue_seconds + allow_delay
exceeds_max_stale, is_first_time = self.tracker.track_stale_data(
    display_name, max_stale_seconds, total_stale_seconds
)

if exceeds_max_stale:
    if is_first_time:
        # gửi final alert
        self.tracker.record_alert_sent(display_name)
    else:
        # silent mode
```

8. **Track consecutive stale days:**
```python
# Old
last_check = self.consecutive_stale_days.get(display_name)
if last_check is None:
    self.consecutive_stale_days[display_name] = (current_date, 1)
else:
    last_date, count = last_check
    if last_date != current_date:
        new_count = count + 1
        self.consecutive_stale_days[display_name] = (current_date, new_count)
        if new_count >= 2:
            self.low_activity_symbols.add(display_name)
            # log

# New
consecutive_days, became_low_activity = self.tracker.track_consecutive_stale_days(
    display_name, low_activity_threshold_days=2
)

if became_low_activity:
    # log
```

9. **Get stale count:**
```python
# Old
stale_count = len(self.first_stale_times)

# New
stale_count = self.tracker.get_stale_count()
```

10. **Check holiday pattern:**
```python
# Old
stale_count = len(self.first_stale_times)
total_apis = max(stale_count, 1)
is_suspected_holiday = (not is_data_from_today) and (
    stale_count >= max(2, int(total_apis * 0.5))
)

# New
stale_count = self.tracker.get_stale_count()
total_apis = max(stale_count, 1)
is_suspected_holiday = self.tracker.check_holiday_pattern(
    current_date, is_data_from_today, total_apis
)
```

11. **Last holiday alert date:**
```python
# Old
if self.last_holiday_alert_date != current_date:
    ...
    self.last_holiday_alert_date = current_date

# New
if self.tracker.last_holiday_alert_date != current_date:
    ...
    self.tracker.last_holiday_alert_date = current_date
```

## Lợi ích

1. **Code dễ maintain:** Logic tracking tập trung ở một nơi
2. **Dễ mở rộng:** Thêm checker mới chỉ cần khởi tạo AlertTracker
3. **Dễ test:** Test AlertTracker độc lập với checker logic
4. **Consistent behavior:** Tất cả checker xử lý tracking giống nhau
5. **Giảm code duplicate:** Không cần copy-paste logic tracking giữa các checker

## Testing

Sau khi refactor xong check_database và check_disk, cần test:

1. Alert frequency throttling hoạt động đúng
2. Silent mode khi vượt max_stale_seconds
3. Low-activity detection sau 2 ngày liên tiếp
4. Empty data warning và auto-silent sau 30 phút (API only)
5. Holiday pattern detection
6. Reset tracking khi data fresh trở lại
7. Outside schedule logging

## Ghi chú

- AlertTracker class là stateful và được persist trong suốt lifetime của checker instance
- Không cần persistence across process restarts (hiện tại)
- Nếu cần persistence, có thể thêm serialize/deserialize methods vào AlertTracker
