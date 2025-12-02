API_CONFIG = {
    "gold-data": {
        "symbols": None,  # Không có symbol
        "uri": "http://192.168.110.164:8010/gold-data/?day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "timezone_offset": 7,
        "allow_delay": 60,
        "check_frequency": 10,
        "alert_frequency": 60,
        "valid_schedule": {
            "days": [0, 1, 2, 3, 4],
            "hours": ["00:00-23:59"],
        },
    },
    # "other-data": {
    #     "symbols": [
    #         "vxx",
    #         "sp500",
    #         "dji",
    #         "usdvnd",
    #         "nikkei",
    #         "csi_300",
    #         "hang_seng",
    #         "dow_jones",
    #         "dxy",
    #         "oxy",
    #         "nasdaq",
    #         "kospi",
    #     ],
    #     "uri": "http://192.168.110.164:8010/crypto/other-data/?symbol={symbol}&day=0",
    #     "record_pointer": 0,
    #     "column_to_check": "datetime",
    #     "timezone_offset": 7,
    #     "allow_delay": 60,
    #     "check_frequency": 5,
    #     "alert_frequency": 60,
    #     "valid_schedule": {
    #         "days": None,
    #         "hours": "07:00-23:00",
    #     },
    # },
    "cmc": {
        "symbols": ["ETH", "BNB", "XRP"],
        "uri": "http://192.168.110.164:8010/crypto/cmc/?symbol={symbol}&day=0",
        "record_pointer": 0,
        "column_to_check": "datetime",
        "timezone_offset": 0,
        "allow_delay": 30 * 60,
        "check_frequency": 60,
        "alert_frequency": 60,
        "valid_schedule": None,
    },
    # "funding-rate": {
    #     "symbols": ["BTC", "ETH", "BNB", "XRP"],
    #     "uri": "http://192.168.110.164:8010/crypto/cmc/?symbol={symbol}&day=0",
    #     "record_pointer": 0,
    #     "column_to_check": "datetime",
    #     "allow_delay": 8 * 60 * 60,
    #     "check_frequency": 60,
    #     "alert_frequency": 60,
    #     "valid_schedule": None,
    # },
}


PLATFORM_CONFIG = {
    "discord": {
        "webhooks_url": "https://discord.com/api/webhooks/1444980293542088786/JhmtaTkgngBYnwbA827wBKfymjnUouliRU0Ktgy1BrsWfge0BEAJSj0kq8RQxr_O7y45",
        "is_primary": True,
    },
    "telegram": {"bot_token": "", "chat_id": "", "is_primary": False},
}


# PostgreSQL Configuration
POSTGRE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "your_database_name",
    "user": "your_username",
    "password": "your_password",
}

# MongoDB Configuration
MONGO_CONFIG = {
    "host": "192.168.110.164",
    "port": 27017,
    "database": "your_database_name",
    "username": "your_username",
    "password": "your_password",
}


DATABASE_CONFIG = {
    # "postgres-users": {
    #     "symbols": None,
    #     "uri": f"postgresql://{POSTGRE_CONFIG['user']}:{POSTGRE_CONFIG['password']}@{POSTGRE_CONFIG['host']}:{POSTGRE_CONFIG['port']}/{POSTGRE_CONFIG['database']}",
    #     "record_pointer": 0,
    #     "column_to_check": "datetime",
    #     "timezone_offset": 7,
    #     "allow_delay": 60,
    #     "check_frequency": 10,
    #     "alert_frequency": 60,
    #     "valid_schedule": {
    #         "days": [0, 1, 2, 3, 4],
    #         "hours": ["00:00-23:59"],
    #     },
    # },
    # "mongo-trades": {
    #     "symbols": ["BTC", "ETH"],
    #     "uri": f"mongodb://{MONGO_CONFIG['username']}:{MONGO_CONFIG['password']}@{MONGO_CONFIG['host']}:{MONGO_CONFIG['port']}/{MONGO_CONFIG['database']}",
    #     "record_pointer": 0,
    #     "column_to_check": "timestamp",
    #     "timezone_offset": 0,
    #     "allow_delay": 30 * 60,
    #     "check_frequency": 60,
    #     "alert_frequency": 60,
    #     "valid_schedule": None,
    # },
}
