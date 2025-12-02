import requests
from datetime import datetime, timedelta

r = requests.get(url="http://192.168.110.164:8010/crypto/cmc/?symbol=ETH&day=0")

datetime_test = r.json()["data"][0]["datetime"]
dt = datetime.strptime(datetime_test, "%Y-%m-%d %H:%M:%S")

datetime_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(datetime_now)
print(dt + timedelta(seconds=10))
