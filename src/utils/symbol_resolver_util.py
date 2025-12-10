"""
Utility để tự động resolve symbols từ database khi API config có symbols: null
"""

import os
import json
from datetime import datetime, timedelta
from configs.database_config import DatabaseManager
from utils.load_config_util import LoadConfigUtil
from configs.logging_config import LoggerConfig


class SymbolResolverUtil:
    """Tự động lấy symbols từ database cho API config"""

    logger = LoggerConfig.logger_config("SymbolResolverUtil")

    # Singleton DatabaseConfig instance - reuse across all queries
    _db_connector = None

    # Cache directory
    CACHE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache"
    )

    # Cache expiry: 24 hours (symbols thường không thay đổi thường xuyên)
    CACHE_EXPIRY_HOURS = 24

    @staticmethod
    def _get_db_connector():
        """Get or create DatabaseManager singleton instance"""
        if SymbolResolverUtil._db_connector is None:
            SymbolResolverUtil._db_connector = DatabaseManager()
        return SymbolResolverUtil._db_connector

    @staticmethod
    def _get_cache_file_path(api_name):
        """Tạo đường dẫn cache file cho api_name"""
        os.makedirs(SymbolResolverUtil.CACHE_DIR, exist_ok=True)
        return os.path.join(SymbolResolverUtil.CACHE_DIR, f"symbols_{api_name}.json")

    @staticmethod
    def _load_symbols_from_cache(api_name):
        """
        Load symbols từ cache file nếu còn valid

        Returns:
            list hoặc None nếu cache không tồn tại hoặc expired
        """
        cache_file = SymbolResolverUtil._get_cache_file_path(api_name)

        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Kiểm tra expiry time
            cached_time = datetime.fromisoformat(cache_data.get("cached_at", ""))
            expiry_time = cached_time + timedelta(
                hours=SymbolResolverUtil.CACHE_EXPIRY_HOURS
            )

            if datetime.now() > expiry_time:
                SymbolResolverUtil.logger.info(
                    f"[{api_name}] Cache đã hết hạn (cached: {cached_time}, expiry: {expiry_time})"
                )
                return None

            symbols = cache_data.get("symbols", [])
            SymbolResolverUtil.logger.info(
                f"[{api_name}] Đọc {len(symbols)} symbols từ cache (cached: {cached_time})"
            )
            return symbols

        except Exception as e:
            SymbolResolverUtil.logger.warning(f"[{api_name}] Lỗi đọc cache: {e}")
            return None

    @staticmethod
    def _save_symbols_to_cache(api_name, symbols):
        """Lưu symbols vào cache file"""
        cache_file = SymbolResolverUtil._get_cache_file_path(api_name)

        try:
            cache_data = {
                "api_name": api_name,
                "cached_at": datetime.now().isoformat(),
                "symbols": symbols,
                "count": len(symbols),
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            SymbolResolverUtil.logger.info(
                f"[{api_name}] Đã cache {len(symbols)} symbols vào {cache_file}"
            )
        except Exception as e:
            SymbolResolverUtil.logger.error(f"[{api_name}] Lỗi ghi cache: {e}")

    @staticmethod
    def get_symbols_from_database(api_name):
        """
        Lấy danh sách symbols từ database config nếu có cùng tên
        Sử dụng cache để tránh query DISTINCT liên tục

        Args:
            api_name: Tên API config (vd: "cmc", "etf_candlestick")

        Returns:
            list: Danh sách symbols hoặc None nếu không tìm thấy
        """
        try:
            # Bước 1: Kiểm tra cache trước
            cached_symbols = SymbolResolverUtil._load_symbols_from_cache(api_name)
            if cached_symbols is not None:
                return cached_symbols

            # Bước 2: Nếu không có cache, query từ database
            SymbolResolverUtil.logger.info(
                f"[{api_name}] Cache không tồn tại hoặc đã hết hạn, query từ database..."
            )

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

            # Bước 3: Lưu kết quả vào cache
            if symbols:
                SymbolResolverUtil._save_symbols_to_cache(api_name, symbols)

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
                "database": {
                    "type": "postgresql",
                    "database": database,
                    "table": table_name,
                }
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

        1. Nếu symbols.auto_sync = true:
           - Tự động lấy symbols từ database (phải có database config cùng tên)
           - Bỏ qua symbols.values trong config (nếu có)

        2. Nếu symbols.auto_sync = false hoặc không có:
           - Dùng symbols.values được định nghĩa thủ công trong config
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
                    f"Kiểm tra database config hoặc chuyển sang auto_sync=false để nhập thủ công."
                )
                return []

        # Case 2: auto_sync = false → Dùng symbols thủ công
        elif auto_sync_symbols is False:
            if (
                symbols_values is not None
                and isinstance(symbols_values, list)
                and len(symbols_values) > 0
            ):
                SymbolResolverUtil.logger.info(
                    f"[{api_name}] symbols.auto_sync=false, sử dụng {len(symbols_values)} symbols thủ công: {symbols_values}"
                )
                return symbols_values
            else:
                SymbolResolverUtil.logger.warning(
                    f"[{api_name}] symbols.auto_sync=false nhưng không có symbols.values được định nghĩa. "
                    f'Vui lòng thêm "values": ["SYMBOL1", "SYMBOL2"] vào config.'
                )
                return []

        # Case 3: auto_sync = null hoặc không có → API không cần symbols
        else:
            SymbolResolverUtil.logger.info(
                f"[{api_name}] symbols.auto_sync=null, API không cần symbols"
            )
            return None
