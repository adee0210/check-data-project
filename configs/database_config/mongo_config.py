"""MongoDB Connector - Kết nối và query MongoDB"""

from typing import Any, Dict, Optional
from datetime import datetime
from configs.database_config.base_db import BaseDatabaseConnector


class MongoDBConnector(BaseDatabaseConnector):
    """
    MongoDB connector implementation

    Hỗ trợ:
    - Connection pooling
    - Query tối ưu với projection
    - Authentication
    """

    def __init__(self, logger):
        super().__init__(logger)
        self.client = None
        self.db = None

    def connect(self, config: Dict[str, Any]) -> Any:
        """
        Kết nối đến MongoDB

        Args:
            config: Dict chứa:
                - host: MongoDB host
                - port: MongoDB port (default: 27017)
                - database: Database name
                - username: Optional username
                - password: Optional password
                - auth_source: Auth source (default: "admin")

        Returns:
            MongoDB database object

        Raises:
            ConnectionError: Nếu không thể kết nối
        """
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError(
                f"Thiếu thư viện MongoDB. "
                f"Cài đặt: pip install {self.get_required_package()}"
            )

        # Validate required fields
        self.validate_config(config, ["host", "database"])

        host = config["host"]
        port = config.get("port", 27017)
        database = config["database"]
        username = config.get("username")
        password = config.get("password")
        auth_source = config.get("auth_source", "admin")

        # Build connection URI
        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource={auth_source}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        try:
            self.client = MongoClient(uri)
            self.db = self.client[database]

            # Test connection
            self.db.list_collection_names()

            self.connection = self.db
            return self.db

        except Exception as e:
            self.logger.error(f"Lỗi kết nối MongoDB: {str(e)}")
            raise ConnectionError(f"Không thể kết nối MongoDB: {str(e)}")

    def query(self, config: Dict[str, Any], symbol: Optional[str] = None) -> datetime:
        """
        Query MongoDB để lấy timestamp mới nhất/cũ nhất

        Args:
            config: Dict chứa:
                - collection_name: Collection name
                - column_to_check: Field chứa timestamp
                - record_pointer: 0 (mới nhất) hoặc -1 (cũ nhất)
                - symbol_column: Optional field chứa symbol

            symbol: Optional symbol để filter

        Returns:
            datetime object

        Raises:
            ValueError: Nếu thiếu config hoặc không có kết quả
        """
        if not self.is_connected():
            raise ConnectionError("Chưa kết nối đến MongoDB")

        # Validate required fields
        self.validate_config(config, ["collection_name", "column_to_check"])

        collection_name = config["collection_name"]
        column_to_check = config["column_to_check"]
        record_pointer = config.get("record_pointer", 0)
        symbol_column = config.get("symbol_column")

        collection = self.db[collection_name]

        # Build query filter
        query_filter = {}
        if symbol and symbol_column:
            query_filter[symbol_column] = symbol

        # Determine sort direction
        if record_pointer == 0:
            # Lấy bản ghi mới nhất: sort descending
            sort_direction = -1
        elif record_pointer == -1:
            # Lấy bản ghi cũ nhất: sort ascending
            sort_direction = 1
        else:
            # Fallback
            sort_direction = -1

        # Projection để chỉ lấy field cần thiết (tối ưu performance)
        projection = {column_to_check: 1, "_id": 0}

        try:
            # Query với projection và sort
            result = (
                collection.find(query_filter, projection)
                .sort(column_to_check, sort_direction)
                .limit(1)
            )

            doc = next(result, None)
            if doc and column_to_check in doc:
                latest_time = doc[column_to_check]

                # Convert to datetime if needed
                if isinstance(latest_time, datetime):
                    return latest_time
                elif isinstance(latest_time, str):
                    # Xử lý string datetime
                    from utils.convert_datetime_util import ConvertDatetimeUtil

                    converted = ConvertDatetimeUtil.convert_str_to_datetime(latest_time)
                    if converted:
                        return converted
                    else:
                        raise ValueError(
                            f"Không thể parse string datetime: {latest_time}"
                        )
                elif isinstance(latest_time, (int, float)):
                    return datetime.fromtimestamp(latest_time)
                else:
                    raise ValueError(
                        f"Không thể convert {type(latest_time)} thành datetime"
                    )
            else:
                raise ValueError("Query không trả về kết quả")

        except StopIteration:
            raise ValueError("Collection rỗng hoặc không có document phù hợp")
        except Exception as e:
            self.logger.error(f"Lỗi query MongoDB: {str(e)}")
            raise

    def close(self) -> None:
        """
        Đóng MongoDB connection
        """
        try:
            if self.client:
                self.client.close()
                self.logger.info("Đã đóng kết nối MongoDB")
        except Exception as e:
            self.logger.error(f"Lỗi đóng kết nối MongoDB: {str(e)}")
        finally:
            self.client = None
            self.db = None
            self.connection = None

    def get_required_package(self) -> str:
        """
        Trả về package name cần cài đặt

        Returns:
            "pymongo"
        """
        return "pymongo"

    def get_distinct_symbols(self, collection_name: str, symbol_column: str) -> list:
        """
        Lấy danh sách unique symbols từ collection

        Args:
            collection_name: Collection name
            symbol_column: Column chứa symbol

        Returns:
            Sorted list of unique symbols
        """
        if not self.is_connected():
            raise ConnectionError("Chưa kết nối đến MongoDB")

        try:
            collection = self.db[collection_name]
            symbols = collection.distinct(symbol_column)
            return sorted(symbols)
        except Exception as e:
            self.logger.error(f"Lỗi lấy DISTINCT symbols từ MongoDB: {str(e)}")
            raise
