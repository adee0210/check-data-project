from configs.logging_config import LoggerConfig
from urllib.parse import urlparse


class DatabaseConfig:
    def __init__(self):
        self.logger = LoggerConfig.logger_config("DatabaseConnector")
        self.connections = {}

    def _parse_uri(self, uri):
        """
        Parse database URI

        Args:
            uri: Connection string (postgresql://... hoặc mongodb://...)

        Returns:
            dict với db_type và connection info
        """
        parsed = urlparse(uri)

        db_type = parsed.scheme
        if db_type not in ["postgresql", "mongodb"]:
            raise ValueError(f"Database type không được hỗ trợ: {db_type}")

        config = {
            "db_type": db_type,
            "host": parsed.hostname,
            "port": parsed.port,
            "database": parsed.path.lstrip("/"),
            "username": parsed.username,
            "password": parsed.password,
        }

        return config

    def _build_connection_config(self, db_type, db_config):
        """
        Build connection config từ POSTGRE_CONFIG hoặc MONGO_CONFIG
        Có thể override database từ db_config

        Args:
            db_type: postgresql hoặc mongodb
            db_config: Config từ DATABASE_CONFIG (có thể chứa database override)

        Returns:
            dict connection config
        """
        from utils.load_config_util import LoadConfigUtil

        POSTGRE_CONFIG = LoadConfigUtil.load_json_to_variable(
            "config.json", "POSTGRE_CONFIG"
        )
        MONGO_CONFIG = LoadConfigUtil.load_json_to_variable(
            "config.json", "MONGO_CONFIG"
        )

        if db_type == "postgresql":
            return {
                "db_type": "postgresql",
                "host": POSTGRE_CONFIG["host"],
                "port": POSTGRE_CONFIG["port"],
                "database": db_config.get("database", POSTGRE_CONFIG["database"]),
                "username": POSTGRE_CONFIG["user"],
                "password": POSTGRE_CONFIG["password"],
            }
        elif db_type == "mongodb":
            return {
                "db_type": "mongodb",
                "host": MONGO_CONFIG["host"],
                "port": MONGO_CONFIG["port"],
                "database": db_config.get(
                    "database", MONGO_CONFIG.get("database", "test")
                ),
                "username": MONGO_CONFIG.get("username"),
                "password": MONGO_CONFIG.get("password"),
                "auth_source": MONGO_CONFIG.get("auth_source", "admin"),
            }
        else:
            raise ValueError(f"Database type không được hỗ trợ: {db_type}")

    def connect(self, db_name, db_config):
        """
        Tạo hoặc lấy connection đến database

        Args:
            db_name: Tên database trong config
            db_config: Dict chứa db_type, database và các thông tin khác

        Returns:
            Database connection object hoặc None nếu lỗi
        """
        if db_name in self.connections:
            return self.connections[db_name]

        db_type = db_config.get("db_type")
        if not db_type:
            self.logger.error(f"Thiếu db_type cho database: {db_name}")
            return None

        try:
            connection_config = self._build_connection_config(db_type, db_config)

            if db_type == "postgresql":
                conn = self._connect_postgresql(connection_config)
                self.connections[db_name] = conn
                self.logger.info(
                    f"Kết nối PostgreSQL thành công: {db_name} -> {connection_config['database']}"
                )
                return conn

            elif db_type == "mongodb":
                db = self._connect_mongodb(connection_config)
                self.connections[db_name] = db
                self.logger.info(
                    f"Kết nối MongoDB thành công: {db_name} -> {connection_config['database']}"
                )
                return db

        except ImportError as e:
            self.logger.error(
                f"Thiếu thư viện cho {db_type}. "
                f"Vui lòng cài đặt: pip install {self._get_required_package(db_type)}"
            )
            return None
        except Exception as e:
            self.logger.error(f"Lỗi kết nối database {db_name}: {str(e)}")
            return None

    def _connect_postgresql(self, config):
        """Kết nối PostgreSQL"""
        import psycopg2

        conn = psycopg2.connect(
            host=config.get("host"),
            port=config.get("port", 5432),
            database=config.get("database"),
            user=config.get("username"),
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
        auth_source = config.get("auth_source", "admin")

        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource={auth_source}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        client = MongoClient(uri)
        db = client[database]
        db.list_collection_names()

        return db

    def _get_required_package(self, db_type):
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
        if not db_type:
            raise ValueError(f"Thiếu db_type cho database {db_name}")

        connection = self.connect(db_name, db_config)

        if connection is None:
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
        """Query PostgreSQL lấy bản ghi mới nhất theo column_to_check"""
        column_to_check = db_config.get("column_to_check", "datetime")
        symbol_column = db_config.get("symbol_column")

        table_name = db_config.get("table_name")
        if not table_name:
            raise ValueError("Thiếu table_name trong config")

        query = f"SELECT {column_to_check} FROM {table_name}"
        if symbol and symbol_column:
            query += f" WHERE {symbol_column} = '{symbol}'"
        query += f" ORDER BY {column_to_check} DESC LIMIT 1"

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

            if result:
                latest_time = result[0]
                return latest_time
            else:
                raise ValueError("Query không trả về kết quả")

    def _query_mongodb(self, db, db_config, symbol=None):
        """Query MongoDB lấy bản ghi mới nhất theo column_to_check"""
        column_to_check = db_config.get("column_to_check", "timestamp")
        symbol_column = db_config.get("symbol_column")

        collection_name = db_config.get("collection_name")
        if not collection_name:
            raise ValueError("Thiếu collection_name trong config")

        collection = db[collection_name]
        query_filter = {}
        if symbol and symbol_column:
            query_filter[symbol_column] = symbol

        result = collection.find(query_filter).sort(column_to_check, -1).limit(1)

        doc = next(result, None)
        if doc:
            latest_time = doc.get(column_to_check)
            if latest_time:
                return latest_time
            else:
                raise ValueError(
                    f"Field '{column_to_check}' không tồn tại trong document"
                )
        else:
            raise ValueError("Query không trả về kết quả")

    def close(self, db_name=None):
        """
        Đóng database connection

        Args:
            db_name: Tên database cần đóng. Nếu None, đóng tất cả
        """
        if db_name:
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
            if connection is not None:
                return True, f"Kết nối thành công đến {db_name}"
            else:
                return False, f"Không thể kết nối đến {db_name}"
        except Exception as e:
            return False, f"Lỗi: {str(e)}"
