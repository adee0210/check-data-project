"""
Utility để tự động resolve symbols từ database khi API config có symbols: null
"""

from configs.database_config import DatabaseConfig
from utils.load_config_util import LoadConfigUtil
from configs.logging_config import LoggerConfig


class SymbolResolverUtil:
    """Tự động lấy symbols từ database cho API config"""

    logger = LoggerConfig.logger_config("SymbolResolverUtil")

    # Singleton DatabaseConfig instance - reuse across all queries
    _db_connector = None

    @staticmethod
    def _get_db_connector():
        """Get or create DatabaseConfig singleton instance"""
        if SymbolResolverUtil._db_connector is None:
            SymbolResolverUtil._db_connector = DatabaseConfig()
        return SymbolResolverUtil._db_connector

    @staticmethod
    def get_symbols_from_database(api_name):
        """
        Lấy danh sách symbols từ database config nếu có cùng tên

        Args:
            api_name: Tên API config (vd: "cmc", "etf_candlestick")

        Returns:
            list: Danh sách symbols hoặc None nếu không tìm thấy
        """
        try:
            # Load database config
            db_config_all = LoadConfigUtil.load_json_to_variable(
                "check_database_config.json"
            )

            # Kiểm tra xem có database config cùng tên không
            if api_name not in db_config_all:
                return None

            db_config = db_config_all[api_name]
            symbol_column = db_config.get("symbol_column")

            # Nếu database không có symbol_column thì không thể lấy symbols
            if not symbol_column:
                SymbolResolverUtil.logger.warning(
                    f"Database config '{api_name}' không có symbol_column, không thể tự động lấy symbols"
                )
                return None

            # Lấy thông tin kết nối database
            db_type = db_config.get("db_type")
            database = db_config.get("database")

            if db_type == "mongodb":
                collection_name = db_config.get("collection_name")
                symbols = SymbolResolverUtil._get_symbols_from_mongodb(
                    database, collection_name, symbol_column
                )
            elif db_type == "postgresql":
                table_name = db_config.get("table_name")
                symbols = SymbolResolverUtil._get_symbols_from_postgresql(
                    database, table_name, symbol_column
                )
            else:
                return None

            if symbols:
                SymbolResolverUtil.logger.info(
                    f"Đã lấy được {len(symbols)} symbols từ database '{api_name}': {symbols}"
                )
            else:
                SymbolResolverUtil.logger.warning(
                    f"Database '{api_name}' chưa có dữ liệu hoặc không có symbols"
                )

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
                "db_type": "mongodb",
                "database": database,
                "collection_name": collection_name,
            }

            # Kết nối MongoDB (reuse existing connection nếu có)
            db = db_connector.connect(f"resolver_{database}", db_config)
            if db is None:
                SymbolResolverUtil.logger.error(
                    f"Không thể kết nối MongoDB: {database}"
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
            # Reuse DatabaseConfig singleton instance
            db_connector = SymbolResolverUtil._get_db_connector()

            # Build config cho PostgreSQL connection
            db_config = {
                "db_type": "postgresql",
                "database": database,
                "table_name": table_name,
            }

            # Kết nối PostgreSQL (reuse existing connection nếu có)
            conn = db_connector.connect(f"resolver_{database}", db_config)
            if conn is None:
                SymbolResolverUtil.logger.error(
                    f"Không thể kết nối PostgreSQL: {database}"
                )
                return []

            # Query distinct symbols
            query = f"SELECT DISTINCT {symbol_column} FROM {table_name} ORDER BY {symbol_column}"
            cursor = conn.cursor()
            cursor.execute(query)

            symbols = [row[0] for row in cursor.fetchall()]

            # Đóng cursor (nhưng KHÔNG đóng connection - để reuse)
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

        1. Nếu auto_sync_symbols = true:
           - Tự động lấy symbols từ database (phải có database config cùng tên)
           - Bỏ qua symbols trong config (nếu có)

        2. Nếu auto_sync_symbols = false hoặc không có:
           - Dùng symbols được định nghĩa thủ công trong config
           - Nếu không có symbols → skip API này

        3. Nếu auto_sync_symbols = null:
           - API không cần symbols (ví dụ: gold-data)

        Args:
            api_name: Tên API config
            api_config: Dict config của API

        Returns:
            list: Danh sách symbols, hoặc None nếu API không cần symbols
        """
        auto_sync_symbols = api_config.get("auto_sync_symbols")

        # Case 1: auto_sync_symbols = true → Tự động lấy từ database
        if auto_sync_symbols is True:
            SymbolResolverUtil.logger.info(
                f"[{api_name}] auto_sync_symbols=true, tự động lấy symbols từ database..."
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
                    f"Kiểm tra database config hoặc chuyển sang auto_sync_symbols=false để nhập thủ công."
                )
                return []

        # Case 2: auto_sync_symbols = false → Dùng symbols thủ công
        elif auto_sync_symbols is False:
            symbols = api_config.get("symbols")

            if symbols is not None and isinstance(symbols, list) and len(symbols) > 0:
                SymbolResolverUtil.logger.info(
                    f"[{api_name}] auto_sync_symbols=false, sử dụng {len(symbols)} symbols thủ công: {symbols}"
                )
                return symbols
            else:
                SymbolResolverUtil.logger.warning(
                    f"[{api_name}] auto_sync_symbols=false nhưng không có symbols được định nghĩa. "
                    f'Vui lòng thêm \'symbols\': ["SYMBOL1", "SYMBOL2"] vào config.'
                )
                return []

        # Case 3: auto_sync_symbols = null hoặc không có → API không cần symbols
        else:
            SymbolResolverUtil.logger.info(
                f"[{api_name}] Không có auto_sync_symbols, API không cần symbols"
            )
            return None
