import requests
from datetime import datetime
from src.utils.convert_datetime_util import ConvertDatetimeUtil

# Test với CMC BNB
uri = "http://192.168.110.164:8010/crypto/cmc/?symbol=BNB&day=0"
timezone_offset = 0  # CMC là GMT+0

print(f"=== TEST THỜI GIAN CMC BNB ===")
print(f"URI: {uri}")
print(f"Timezone offset của data: GMT+{timezone_offset}")
print()

# Lấy data từ API
r = requests.get(url=uri)
data = r.json()["data"][0]
datetime_str = data["datetime"]

print(f"1. Datetime từ API (raw): {datetime_str}")

# Convert string to datetime
dt = ConvertDatetimeUtil.convert_str_to_datetime(datetime_str)
print(f"2. Sau khi parse: {dt}")

# Convert timezone nếu cần
if timezone_offset != 7:
    dt_converted = ConvertDatetimeUtil.convert_utc_to_local(
        dt, timezone_offset=7 - timezone_offset
    )
    print(f"3. Sau khi convert sang GMT+7: {dt_converted}")
else:
    dt_converted = dt
    print(f"3. Không cần convert (đã là GMT+7)")

# So sánh với thời gian hiện tại
current_time = datetime.now()
print(f"4. Thời gian hiện tại (GMT+7): {current_time}")

# Tính chênh lệch
time_diff = (current_time - dt_converted).total_seconds()
minutes = int(time_diff // 60)
seconds = int(time_diff % 60)

print()
print(f"=== KẾT QUẢ ===")
print(f"Data cũ: {minutes} phút {seconds} giây ({int(time_diff)} giây)")
print(f"Ngưỡng cho phép: 15 phút (900 giây)")
print(f"Quá hạn: {max(0, minutes - 15)} phút {max(0, int(time_diff) - 900)} giây")

if time_diff > 900:
    print(f"⚠️  PHẢI BÁO CẢNH BÁO (data cũ hơn 15 phút)")
else:
    print(f"✅ CHƯA CẦN BÁO (data còn trong ngưỡng 15 phút)")
