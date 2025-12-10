"""
Database Manager

Unified interface to manage multiple database connectors
Factory pattern for creating appropriate connector instances
"""

from typing import Any, Dict, Optional
from datetime import datetime
from configs.logging_config import LoggerConfig
from .base_db import BaseDatabaseConnector
from .mongo_config import MongoDBConnector
from .postgres_config import PostgreSQLConnector


class DatabaseManager:
    """
    Database Manager - Quản lý tất cả database connections

    Features:
    - Connection pooling (reuse connections)
    - Auto-reload config from common_config.json
    - Factory pattern for creating connectors
    - Easy to extend with new database types

    Usage:
        manager = DatabaseManager()

        # Query database
        latest_time = manager.query("db_name", db_config, symbol="BTC")

        # Close connections
        manager.close("db_name")  # Close specific
        manager.close()  # Close all
    """

    CONNECTOR_REGISTRY = {
        "mongodb": MongoDBConnector,
        "postgresql": PostgreSQLConnector,
        # Dễ dàng thêm: "mysql": MySQLConnector,
    }

    def __init__(self):
        """
        Initialize Database Manager
        """
        self.logger = LoggerConfig.logger_config("DatabaseManager")
        self.connectors: Dict[str, BaseDatabaseConnector] = {}

    def _get_connection_config(
        self, db_type: str, db_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build connection config từ common_config.json

        Args:
            db_type: "mongodb", "postgresql".
            db_config: Config từ data_sources_config.json

        Returns:
            Dict connection config
        """
        from utils.load_config_util import LoadConfigUtil

        common_config = LoadConfigUtil.load_json_to_variable("common_config.json")

        # Extract database name từ config
        db_cfg = db_config.get("database", {})
        database_name = (
            db_cfg.get("database")
            if isinstance(db_cfg, dict)
            else db_config.get("database")
        )

        if db_type == "postgresql":
            postgres_config = common_config["POSTGRE_CONFIG"]
            return {
                "host": postgres_config["host"],
                "port": postgres_config["port"],
                "database": database_name or postgres_config["database"],
                "username": postgres_config["user"],
                "password": postgres_config["password"],
            }

        elif db_type == "mongodb":
            mongo_config = common_config["MONGO_CONFIG"]
            return {
                "host": mongo_config["host"],
                "port": mongo_config["port"],
                "database": database_name or mongo_config.get("database", "test"),
                "username": mongo_config.get("username"),
                "password": mongo_config.get("password"),
                "auth_source": mongo_config.get("auth_source", "admin"),
            }

        # Thêm các database khác ở đây theo format chung
        # elif db_type == "mysql":
        #     mysql_config = common_config["MYSQL_CONFIG"]
        #     return {...}

        else:
            raise ValueError(f"Database type không được hỗ trợ: {db_type}")

    def _create_connector(self, db_type: str) -> BaseDatabaseConnector:
        """
        Factory method: Tạo connector instance theo db_type

        Args:
            db_type: Database type ("mongodb", "postgresql", etc.)

        Returns:
            BaseDatabaseConnector instance

        Raises:
            ValueError: Nếu db_type không được hỗ trợ
        """
        connector_class = self.CONNECTOR_REGISTRY.get(db_type)

        if not connector_class:
            supported_types = ", ".join(self.CONNECTOR_REGISTRY.keys())
            raise ValueError(
                f"Database type '{db_type}' không được hỗ trợ. "
                f"Các loại hỗ trợ: {supported_types}"
            )

        return connector_class(self.logger)

    def connect(self, db_name: str, db_config: Dict[str, Any]) -> BaseDatabaseConnector:
        """
        Tạo hoặc lấy existing connector

        Args:
            db_name: Tên database (unique identifier)
            db_config: Config từ data_sources_config.json

        Returns:
            BaseDatabaseConnector instance

        Raises:
            ValueError: Nếu thiếu database.type
            ConnectionError: Nếu không thể kết nối
        """
        # Reuse existing connector
        if db_name in self.connectors:
            connector = self.connectors[db_name]
            if connector.is_connected():
                return connector

        # Extract database type
        db_cfg = db_config.get("database", {})
        db_type = (
            db_cfg.get("type") if isinstance(db_cfg, dict) else db_config.get("db_type")
        )

        if not db_type:
            raise ValueError(f"Thiếu database.type cho database: {db_name}")

        try:
            # Create new connector
            connector = self._create_connector(db_type)

            # Build connection config
            connection_config = self._get_connection_config(db_type, db_config)

            # Connect
            connector.connect(connection_config)

            # Cache connector
            self.connectors[db_name] = connector

            self.logger.info(f"Kết nối {db_type} thành công: {db_name}")
            return connector

        except ImportError as e:
            connector = self._create_connector(db_type)
            self.logger.error(
                f"Thiếu thư viện cho {db_type}. "
                f"Vui lòng cài đặt: pip install {connector.get_required_package()}"
            )
            raise
        except Exception as e:
            self.logger.error(f"Lỗi kết nối database {db_name}: {str(e)}")
            raise

    def query(
        self, db_name: str, db_config: Dict[str, Any], symbol: Optional[str] = None
    ) -> datetime:
        """
        Query database để lấy timestamp mới nhất/cũ nhất

        Args:
            db_name: Tên database
            db_config: Config từ data_sources_config.json
            symbol: Optional symbol để filter

        Returns:
            datetime object

        Raises:
            ConnectionError: Nếu không thể kết nối
            ValueError: Nếu query không có kết quả
        """
        # Get or create connector
        connector = self.connect(db_name, db_config)

        # Extract query config
        db_cfg = db_config.get("database", {})
        symbols_cfg = db_config.get("symbols", {})

        query_config = {
            "column_to_check": db_cfg.get("column_to_check", "datetime"),
            "record_pointer": db_cfg.get("record_pointer", 0),
            "symbol_column": symbols_cfg.get("column"),
        }

        # Add table/collection name based on db type
        if "collection_name" in db_cfg:
            query_config["collection_name"] = db_cfg["collection_name"]
        elif "table" in db_cfg:
            query_config["table"] = db_cfg["table"]
        else:
            # Fallback to old format
            query_config["collection_name"] = db_config.get("collection_name")
            query_config["table"] = db_config.get("table") or db_config.get(
                "table_name"
            )

        # Execute query
        return connector.query(query_config, symbol)

    def get_distinct_symbols(self, db_name: str, db_config: Dict[str, Any]) -> list:
        """
        Lấy danh sách unique symbols từ database

        Args:
            db_name: Tên database
            db_config: Config từ data_sources_config.json

        Returns:
            Sorted list of unique symbols
        """
        connector = self.connect(db_name, db_config)

        db_cfg = db_config.get("database", {})
        symbols_cfg = db_config.get("symbols", {})

        symbol_column = symbols_cfg.get("column")
        if not symbol_column:
            raise ValueError("Thiếu symbols.column trong config")

        # Get table/collection name
        collection_name = db_cfg.get("collection_name")
        table_name = db_cfg.get("table")

        if hasattr(connector, "get_distinct_symbols"):
            if collection_name:
                return connector.get_distinct_symbols(collection_name, symbol_column)
            elif table_name:
                return connector.get_distinct_symbols(table_name, symbol_column)

        raise ValueError("Connector không hỗ trợ get_distinct_symbols")

    def close(self, db_name: Optional[str] = None) -> None:
        """
        Đóng database connections

        Args:
            db_name: Tên database cần đóng. Nếu None, đóng tất cả
        """
        if db_name:
            # Close specific connector
            if db_name in self.connectors:
                try:
                    self.connectors[db_name].close()
                    del self.connectors[db_name]
                    self.logger.info(f"Đã đóng kết nối: {db_name}")
                except Exception as e:
                    self.logger.error(f"Lỗi đóng kết nối {db_name}: {str(e)}")
        else:
            # Close all connectors
            for name, connector in list(self.connectors.items()):
                try:
                    connector.close()
                    self.logger.info(f"Đã đóng kết nối: {name}")
                except Exception as e:
                    self.logger.error(f"Lỗi đóng kết nối {name}: {str(e)}")

            self.connectors.clear()

    def list_supported_types(self) -> list:
        """
        Liệt kê các database types được hỗ trợ

        Returns:
            List of supported database types
        """
        return list(self.CONNECTOR_REGISTRY.keys())
