API_CONFIG = {
    "gold-data": {
        "symbols": None,  # Không có symbol
        "uri": "http://192.168.110.164:8010/gold-data/?day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "timezone_offset": 7,  # Múi giờ của data (GMT+7)
        "allow_delay": 10,
        "check_frequency": 5,
        "source_platform": "discord",
        "alert_frequency": 10,
        "valid_time": {},
    },
    "other-data": {
        "symbols": [
            "vxx",
            "sp500",
            "dji",
            "usdvnd",
            "nikkei",
            "csi_300",
            "hang_seng",
            "dow_jones",
            "dxy",
            "oxy",
            "nasdaq",
            "kospi",
        ],  # Danh sách symbol cần check
        "uri": "http://192.168.110.164:8010/crypto/other-data/?symbol={symbol}&day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "timezone_offset": 7,  # Múi giờ của data (GMT+7)
        "allow_delay": 60,
        "check_frequency": 5,
        "source_platform": "discord",
        "alert_frequency": 10,
        "valid_time": {},
    },
    "cmc": {
        "symbols": ["BTC", "ETH", "BNB", "XRP"],  # Danh sách symbol cần check
        "uri": "http://192.168.110.164:8010/crypto/cmc/?symbol={symbol}&day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "timezone_offset": 0,  # Múi giờ của data (GMT+0/UTC)
        "allow_delay": 15 * 60,
        "check_frequency": 60,
        "source_platform": "discord",
        "alert_frequency": 10,
        "valid_time": {},
    },
    # "funding-rate": {
    #     "symbols": ["BTC", "ETH", "BNB", "XRP"],  # Danh sách symbol cần check
    #     "uri": "http://192.168.110.164:8010/crypto/cmc/?symbol={symbol}&day=0",
    #     "record_pointer": 0,
    #     "column_to_check": "datetime",
    #     "allow_delay": 15 * 60,
    #     "check_frequency": 60,
    #     "source_platform": "discord",
    #     "alert_frequency": 10,
    #     "valid_time": {},
    # },
}

PLATFORM_CONFIG = {
    "discord": {
        "webhooks_url": "https://discord.com/api/webhooks/1444980293542088786/JhmtaTkgngBYnwbA827wBKfymjnUouliRU0Ktgy1BrsWfge0BEAJSj0kq8RQxr_O7y45",
        "is_primary": True,
    },
    "telegram": {"bot_token": "", "chat_id": "", "is_primary": False},
}
