from configs.logging_config import LoggerConfig


class DatabaseConfig:
    def __init__(self):
        self.logger = LoggerConfig.logger_config("DatabaseConnector")
        self.connections = {}

    def connect(self, db_name, db_config):
        """
        Tạo hoặc lấy connection đến database

        Args:
            db_name: Tên database trong config
            db_config: Dict chứa thông tin kết nối

        Returns:
            Database connection object hoặc None nếu lỗi
        """
        # Nếu đã có connection, trả về luôn
        if db_name in self.connections:
            return self.connections[db_name]

        db_type = db_config.get("db_type")
        connection_config = db_config.get("connection", {})

        try:
            if db_type == "postgresql":
                conn = self._connect_postgresql(connection_config)
                self.connections[db_name] = conn
                self.logger.info(f"✓ Kết nối PostgreSQL thành công: {db_name}")
                return conn

            elif db_type == "mongodb":
                db = self._connect_mongodb(connection_config)
                self.connections[db_name] = db
                self.logger.info(f"✓ Kết nối MongoDB thành công: {db_name}")
                return db

            else:
                self.logger.error(f"✗ Database type không được hỗ trợ: {db_type}")
                return None

        except ImportError as e:
            self.logger.error(
                f"✗ Thiếu thư viện cho {db_type}. "
                f"Vui lòng cài đặt: pip install {self._get_required_package(db_type)}"
            )
            return None
        except Exception as e:
            self.logger.error(f"✗ Lỗi kết nối database {db_name}: {str(e)}")
            return None

    def _connect_postgresql(self, config):
        """Kết nối PostgreSQL"""
        import psycopg2

        conn = psycopg2.connect(
            host=config.get("host"),
            port=config.get("port", 5432),
            database=config.get("database"),
            user=config.get("user"),
            password=config.get("password"),
        )
        return conn

    def _connect_mongodb(self, config):
        """Kết nối MongoDB"""
        from pymongo import MongoClient

        username = config.get("username")
        password = config.get("password")
        host = config.get("host")
        port = config.get("port", 27017)
        database = config.get("database")

        # Tạo connection URI
        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        client = MongoClient(uri)
        db = client[database]

        # Test connection
        db.list_collection_names()

        return db

    def _get_required_package(self, db_type):
        """Trả về tên package cần cài đặt"""
        packages = {
            "postgresql": "psycopg2-binary",
            "mongodb": "pymongo",
        }
        return packages.get(db_type, "unknown")

    def query(self, db_name, db_config, symbol=None):
        """
        Thực hiện query database và trả về datetime mới nhất

        Args:
            db_name: Tên database
            db_config: Config database
            symbol: Symbol (nếu có)

        Returns:
            Datetime object hoặc raise Exception nếu lỗi
        """
        db_type = db_config.get("db_type")
        connection = self.connect(db_name, db_config)

        if not connection:
            raise ConnectionError(f"Không thể kết nối đến database {db_name}")

        try:
            if db_type == "postgresql":
                return self._query_postgresql(connection, db_config, symbol)
            elif db_type == "mongodb":
                return self._query_mongodb(connection, db_config, symbol)
            else:
                raise ValueError(f"Database type không hỗ trợ: {db_type}")

        except Exception as e:
            self.logger.error(f"Lỗi query database {db_name}: {str(e)}")
            raise

    def _query_postgresql(self, connection, db_config, symbol=None):
        """Query PostgreSQL"""
        query = db_config.get("query")
        if symbol:
            query = query.format(symbol=symbol)

        result_column = db_config.get("result_column")

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

            if result:
                # result is a tuple, get first column
                latest_time = result[0]
                return latest_time
            else:
                raise ValueError("Query không trả về kết quả")

    def _query_mongodb(self, db, db_config, symbol=None):
        """Query MongoDB"""
        collection_name = db_config.get("collection")
        query_filter = db_config.get("query", {})

        # Replace symbol in query filter if needed
        if symbol and "{symbol}" in str(query_filter):
            import json

            query_str = json.dumps(query_filter).replace("{symbol}", symbol)
            query_filter = json.loads(query_str)

        result_field = db_config.get("result_field")
        sort = db_config.get("sort", [("_id", -1)])
        limit = db_config.get("limit", 1)

        collection = db[collection_name]
        result = collection.find(query_filter).sort(sort).limit(limit)

        doc = next(result, None)
        if doc:
            latest_time = doc.get(result_field)
            if latest_time:
                return latest_time
            else:
                raise ValueError(f"Field '{result_field}' không tồn tại trong document")
        else:
            raise ValueError("Query không trả về kết quả")

    def close(self, db_name=None):
        """
        Đóng database connection

        Args:
            db_name: Tên database cần đóng. Nếu None, đóng tất cả
        """
        if db_name:
            # Đóng một connection cụ thể
            if db_name in self.connections:
                try:
                    conn = self.connections[db_name]
                    if hasattr(conn, "close"):
                        conn.close()
                    del self.connections[db_name]
                    self.logger.info(f"Đã đóng kết nối database: {db_name}")
                except Exception as e:
                    self.logger.error(f"Lỗi đóng kết nối {db_name}: {str(e)}")
        else:
            # Đóng tất cả connections
            for name, conn in list(self.connections.items()):
                try:
                    if hasattr(conn, "close"):
                        conn.close()
                    self.logger.info(f"Đã đóng kết nối database: {name}")
                except Exception as e:
                    self.logger.error(f"Lỗi đóng kết nối {name}: {str(e)}")
            self.connections.clear()

    def test_connection(self, db_name, db_config):
        """
        Test kết nối database

        Returns:
            (success, message)
        """
        try:
            connection = self.connect(db_name, db_config)
            if connection:
                return True, f"Kết nối thành công đến {db_name}"
            else:
                return False, f"Không thể kết nối đến {db_name}"
        except Exception as e:
            return False, f"Lỗi: {str(e)}"
