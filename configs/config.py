API_CONFIG = {
    "gold_data": {
        "uri": "http://192.168.110.164:8010/gold-data/?day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "allow_delay": 10,
        "check_frequency": 5,
        "source_platform": "discord",
        "alert_frequency": 10,
        "valid_time": {},
    },
    "other_data": {
        "uri": "http://192.168.110.164:8010/crypto/other-data/?symbol=sp500&day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "allow_delay": 10,
        "check_frequency": 5,
        "source_platform": "discord",
        "alert_frequency": 10,
        "valid_time": {},
    },
}

PLATFORM_CONFIG = {
    "discord": {
        "webhooks_url": "https://discord.com/api/webhooks/1444980293542088786/JhmtaTkgngBYnwbA827wBKfymjnUouliRU0Ktgy1BrsWfge0BEAJSj0kq8RQxr_O7y45",
        "is_primary": True,
    },
    "telegram": {"bot_token": "", "chat_id": "", "is_primary": False},
}
