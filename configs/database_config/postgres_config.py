"""PostgreSQL Connector - Kết nối và query PostgreSQL"""

from typing import Any, Dict, Optional
from datetime import datetime
from configs.database_config.base_db import BaseDatabaseConnector


class PostgreSQLConnector(BaseDatabaseConnector):
    """
    PostgreSQL connector implementation
    - Connection pooling
    - Auto-reconnect khi connection bị đóng
    """

    def __init__(self, logger):
        super().__init__(logger)

    def is_connected(self):
        """
        Check xem PostgreSQL connection còn active không

        Returns:
            True nếu connected và active, False nếu không
        """
        if self.connection is None:
            return False

        try:
            # Test connection bằng cách execute simple query
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            # Connection đã bị đóng hoặc không còn hoạt động
            return False

    def connect(self, config):
        """
        Kết nối đến PostgreSQL

        Args:
            config: Dict chứa:
                - host: PostgreSQL host
                - port: PostgreSQL port (5432)
                - database: Database name
                - username: Username
                - password: Password

        Returns:
            psycopg2 connection object

        Raises:
            ConnectionError: Nếu không thể kết nối
        """
        try:
            import psycopg2
        except ImportError:
            raise ImportError(
                "Thiếu thư viện PostgreSQL. Cài đặt dependencies từ requirements.txt"
            )

        # Validate required fields
        self.validate_config(config, ["host", "database", "username", "password"])

        host = config["host"]
        port = config.get("port", 5432)
        database = config["database"]
        username = config["username"]
        password = config["password"]

        try:
            self.connection = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password,
            )

            return self.connection

        except Exception as e:
            self.logger.error(f"Lỗi kết nối PostgreSQL: {str(e)}")
            raise ConnectionError(f"Không thể kết nối PostgreSQL: {str(e)}")

    def query(self, config, symbol):
        """
        Query PostgreSQL để lấy timestamp mới nhất/cũ nhất

        Args:
            config: Dict chứa:
                - table: Table name
                - column_to_check: Column chứa timestamp
                - record_pointer: 0 (mới nhất) hoặc -1 (cũ nhất)
                - symbol_column: Optional column chứa symbol

            symbol: Optional symbol để filter

        Returns:
            datetime object

        Raises:
            ValueError: Nếu thiếu config hoặc không có kết quả
        """
        if not self.is_connected():
            raise ConnectionError(
                "Connection đã bị đóng hoặc chưa kết nối đến PostgreSQL"
            )

        self.validate_config(config, ["table", "column_to_check"])

        table_name = config["table"]
        column_to_check = config["column_to_check"]
        record_pointer = config.get("record_pointer", 0)
        symbol_column = config.get("symbol_column")

        if record_pointer == 0:
            # Lấy bản ghi mới nhất: dùng MAX()
            agg_func = "MAX"
        elif record_pointer == -1:
            # Lấy bản ghi cũ nhất: dùng MIN()
            agg_func = "MIN"
        else:
            # Fallback
            agg_func = "MAX"

        query = f"SELECT {agg_func}({column_to_check}) FROM {table_name}"
        params = []

        if symbol and symbol_column:
            query += f" WHERE {symbol_column} = %s"
            params.append(symbol)

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()

                if result and result[0] is not None:
                    latest_time = result[0]

                    from utils.convert_datetime_util import ConvertDatetimeUtil

                    try:
                        return ConvertDatetimeUtil.convert_str_to_datetime(latest_time)
                    except ValueError as e:
                        raise ValueError(
                            f"Không thể convert {type(latest_time)} ({latest_time}) thành datetime: {e}"
                        )
                else:
                    raise ValueError("Query không trả về kết quả")

        except Exception as e:
            # Kiểm tra nếu là lỗi connection closed
            error_str = str(e).lower()
            if "closed" in error_str or "terminate" in error_str:
                self.logger.error(
                    f"Lỗi query PostgreSQL: {str(e)} - Connection có thể đã bị đóng bởi server"
                )
            else:
                self.logger.error(f"Lỗi query PostgreSQL: {str(e)}")
            raise

    def close(self):
        """
        Đóng PostgreSQL connection
        """
        try:
            if self.connection:
                self.connection.close()
                self.logger.info("Đã đóng kết nối PostgreSQL")
        except Exception as e:
            self.logger.error(f"Lỗi đóng kết nối PostgreSQL: {str(e)}")
        finally:
            self.connection = None

    def get_distinct_symbols(self, table_name, symbol_column):
        """
        Args:
            table_name: Table name
            symbol_column: Column chứa symbol

        Returns:
            Sorted list các giá trị duy nhất của symbol
        """
        if not self.is_connected():
            raise ConnectionError(
                "Connection đã bị đóng hoặc chưa kết nối đến PostgreSQL"
            )

        try:
            query = f"SELECT DISTINCT {symbol_column} FROM {table_name} ORDER BY {symbol_column}"

            with self.connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                return [row[0] for row in results]

        except Exception as e:
            # Kiểm tra nếu là lỗi connection closed
            error_str = str(e).lower()
            if "closed" in error_str or "terminate" in error_str:
                self.logger.error(
                    f"Lỗi lấy DISTINCT symbols từ PostgreSQL: {str(e)} - Connection có thể đã bị đóng bởi server"
                )
            else:
                self.logger.error(f"Lỗi lấy DISTINCT symbols từ PostgreSQL: {str(e)}")
            raise
