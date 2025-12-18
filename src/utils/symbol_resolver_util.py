import os
import json
from datetime import datetime, timedelta
from configs.database_config.database_manager import DatabaseManager
from utils.load_config_util import LoadConfigUtil
from configs.logging_config import LoggerConfig


class SymbolResolverUtil:
    """Tự động lấy symbols từ database cho API config"""

    logger = LoggerConfig.logger_config("SymbolResolverUtil")

    # Singleton DatabaseConfig instance - reuse across all queries
    _db_connector = None

    @staticmethod
    def _get_db_connector():
        """Get or create DatabaseManager singleton instance"""
        if SymbolResolverUtil._db_connector is None:
            SymbolResolverUtil._db_connector = DatabaseManager()
        return SymbolResolverUtil._db_connector

    @staticmethod
    def get_symbols_from_database(api_name):
        """
        Lấy danh sách symbols từ database config nếu có cùng tên
        Luôn query từ database, không dùng cache

        Args:
            api_name: Tên API config (vd: "cmc", "etf_candlestick")

        Returns:
            list: Danh sách symbols hoặc None nếu không tìm thấy
        """
        try:
            SymbolResolverUtil.logger.info(f"[{api_name}] Query symbols từ database...")

            # Load database config từ file chung
            db_config_all = LoadConfigUtil.load_json_to_variable(
                "data_sources_config.json"
            )

            # Kiểm tra xem có database config cùng tên không
            if api_name not in db_config_all:
                return None

            config = db_config_all[api_name]

            # Đọc symbols config mới
            symbols_cfg = config.get("symbols", {})
            symbol_column = symbols_cfg.get("column")

            # Nếu không có symbol_column thì không thể lấy symbols
            if not symbol_column:
                SymbolResolverUtil.logger.warning(
                    f"Config '{api_name}' không có symbols.column, không thể tự động lấy symbols"
                )
                return None

            # Đọc database config mới
            db_cfg = config.get("database", {})
            db_type = db_cfg.get("type")
            database = db_cfg.get("database")

            if db_type == "mongodb":
                collection_name = db_cfg.get("collection_name")
                symbols = SymbolResolverUtil._get_symbols_from_mongodb(
                    database, collection_name, symbol_column
                )
            elif db_type == "postgresql":
                table_name = db_cfg.get("table") or db_cfg.get("table_name")
                symbols = SymbolResolverUtil._get_symbols_from_postgresql(
                    database, table_name, symbol_column
                )
            else:
                return None

            return symbols

        except Exception as e:
            SymbolResolverUtil.logger.error(
                f"Lỗi khi resolve symbols từ database cho {api_name}: {e}"
            )
            return None

    @staticmethod
    def _get_symbols_from_mongodb(database, collection_name, symbol_column):
        """
        Query MongoDB để lấy distinct symbols

        Args:
            database: Tên database
            collection_name: Tên collection
            symbol_column: Tên column chứa symbol

        Returns:
            list: Danh sách symbols
        """
        try:
            # Reuse DatabaseConfig singleton instance
            db_connector = SymbolResolverUtil._get_db_connector()

            # Build config cho MongoDB connection
            db_config = {
                "database": {
                    "type": "mongodb",
                    "database": database,
                    "collection_name": collection_name,
                }
            }

            # Kết nối MongoDB (reuse existing connection nếu có)
            connector = db_connector.connect(f"resolver_{database}", db_config)
            if connector is None:
                SymbolResolverUtil.logger.error(
                    f"Không thể kết nối MongoDB: {database}"
                )
                return []

            # Lấy database object từ connector
            db = connector.connection
            if db is None:
                SymbolResolverUtil.logger.error(
                    f"Connector không có database connection: {database}"
                )
                return []

            # Lấy collection và query distinct symbols
            collection = db[collection_name]
            symbols = collection.distinct(symbol_column)

            # KHÔNG đóng connection - để reuse cho lần sau
            # Connection sẽ được quản lý bởi DatabaseConfig singleton

            # Filter None/empty values và sort
            symbols = [s for s in symbols if s]

            return sorted(symbols) if symbols else []

        except Exception as e:
            SymbolResolverUtil.logger.error(
                f"Lỗi khi query MongoDB ({database}.{collection_name}): {e}"
            )
            return []

    @staticmethod
    def _get_symbols_from_postgresql(database, table_name, symbol_column):
        """
        Query PostgreSQL để lấy distinct symbols

        Args:
            database: Tên database
            table_name: Tên table
            symbol_column: Tên column chứa symbol

        Returns:
            list: Danh sách symbols
        """
        try:
            db_connector = SymbolResolverUtil._get_db_connector()

            # Build config cho PostgreSQL connection
            db_config = {
                "database": {
                    "type": "postgresql",
                    "database": database,
                    "table": table_name,
                }
            }

            # Kết nối PostgreSQL (reuse existing connection nếu có)
            connector = db_connector.connect(f"resolver_{database}", db_config)
            if connector is None:
                SymbolResolverUtil.logger.error(
                    f"Không thể kết nối PostgreSQL: {database}"
                )
                return []

            # Lấy connection object từ connector
            conn = connector.connection
            if conn is None:
                SymbolResolverUtil.logger.error(
                    f"Connector không có database connection: {database}"
                )
                return []

            # Query distinct symbols
            query = f"SELECT DISTINCT {symbol_column} FROM {table_name} ORDER BY {symbol_column}"
            cursor = conn.cursor()
            cursor.execute(query)

            symbols = [row[0] for row in cursor.fetchall()]

            cursor.close()

            return symbols

        except Exception as e:
            SymbolResolverUtil.logger.error(
                f"Lỗi khi query PostgreSQL ({database}.{table_name}): {e}"
            )
            return []

    @staticmethod
    def resolve_api_symbols(api_name, api_config):
        """
        Resolve symbols cho API config với logic mới:

        1. Nếu symbols.auto_sync = true:
           - Tự động lấy symbols từ database (phải có database config cùng tên)
           - Bỏ qua symbols.values trong config (nếu có)

        2. Nếu symbols.auto_sync = false hoặc không có:
           - Dùng symbols.values được định nghĩa trong config
           - Nếu không có symbols.values → skip API này

        3. Nếu symbols.auto_sync = null:
           - API không cần symbols (ví dụ: gold-data)

        Args:
            api_name: Tên API config
            api_config: Dict config của API

        Returns:
            list: Danh sách symbols, hoặc None nếu API không cần symbols
        """
        symbols_cfg = api_config.get("symbols", {})
        auto_sync_symbols = symbols_cfg.get("auto_sync")
        symbols_values = symbols_cfg.get("values")

        # Case 1: auto_sync = true → Tự động lấy từ database
        if auto_sync_symbols is True:
            SymbolResolverUtil.logger.info(
                f"[{api_name}] symbols.auto_sync=true, tự động lấy symbols từ database..."
            )
            auto_symbols = SymbolResolverUtil.get_symbols_from_database(api_name)

            if auto_symbols and len(auto_symbols) > 0:
                SymbolResolverUtil.logger.info(
                    f"[{api_name}] Đã đồng bộ {len(auto_symbols)} symbols từ database: {auto_symbols}"
                )
                return auto_symbols
            else:
                SymbolResolverUtil.logger.warning(
                    f"[{api_name}] Không tìm thấy symbols từ database. "
                    f"Kiểm tra database config hoặc chuyển sang auto_sync=false và tự nhập các cái muốn lấy."
                )
                return []

        # Case 2: auto_sync = false → Dùng symbols tự nhập
        elif auto_sync_symbols is False:
            if (
                symbols_values is not None
                and isinstance(symbols_values, list)
                and len(symbols_values) > 0
            ):
                SymbolResolverUtil.logger.info(
                    f"[{api_name}] symbols.auto_sync=false, sử dụng {len(symbols_values)} symbols tự nhập vào: {symbols_values}"
                )
                return symbols_values
            else:
                SymbolResolverUtil.logger.warning(
                    f"[{api_name}] symbols.auto_sync=false nhưng không có symbols.values được định nghĩa. "
                    f'Hãy thêm "values": ["SYMBOL1", "SYMBOL2"] vào config.'
                )
                return []

        # Case 3: auto_sync = null hoặc không có → API không cần symbols
        else:
            SymbolResolverUtil.logger.info(
                f"[{api_name}] symbols.auto_sync=null, API không cần symbols"
            )
            return None
