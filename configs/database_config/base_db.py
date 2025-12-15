"""Base Database Connector - Interface chung cho tất cả database connectors"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime


class BaseDatabaseConnector(ABC):
    """
    Abstract base class cho tất cả database connectors

    Các subclass phải implement:
    - connect(): Tạo connection
    - query(): Query dữ liệu
    - close(): Đóng connection
    """

    def __init__(self, logger):
        """
        Initialize base connector

        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.connection = None

    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> Any:
        """
        Tạo connection đến database

        Args:
            config: Dict chứa connection parameters

        Returns:
            Connection object

        Raises:
            ConnectionError: Nếu không thể kết nối
        """
        pass

    @abstractmethod
    def query(self, config: Dict[str, Any], symbol: Optional[str] = None) -> datetime:
        """
        Query database để lấy timestamp mới nhất/cũ nhất

        Args:
            config: Dict chứa query parameters (table/collection, column, etc.)
            symbol: Optional symbol để filter

        Returns:
            datetime object của record

        Raises:
            ValueError: Nếu query không trả về kết quả
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Đóng database connection
        """
        pass

    @abstractmethod
    def get_required_package(self) -> str:
        """
        Trả về tên package cần cài đặt

        Returns:
            Package name (e.g., "psycopg2-binary", "pymongo")
        """
        pass

    def is_connected(self) -> bool:
        """
        Check xem connection còn active không

        Subclasses có thể override để check connection status cụ thể hơn

        Returns:
            True nếu connected, False nếu không
        """
        return self.connection is not None

    def validate_config(self, config: Dict[str, Any], required_fields: list) -> None:
        """
        Validate config có đủ required fields không

        Args:
            config: Config dict cần validate
            required_fields: List các fields bắt buộc

        Raises:
            ValueError: Nếu thiếu field bắt buộc
        """
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(f"Thiếu các field bắt buộc: {', '.join(missing_fields)}")
