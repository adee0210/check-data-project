import sys
from pathlib import Path


def find_project_root(current_file, marker="requirements.txt"):
    """
    Tìm thư mục root của project

    Args:
        current_file: File hiện tại
        marker: File đánh dấu root (default: requirements.txt)

    Returns:
        Path object của project root
    """
    current_path = Path(current_file).resolve()
    for parent in current_path.parents:
        if (parent / marker).exists():
            return parent
    return current_path.parent


# Thêm project root vào sys.path để import modules
project_root = find_project_root(__file__, marker="requirements.txt")
sys.path.insert(0, str(project_root))


from check.check_api import CheckAPI
from check.check_database import CheckDatabase
from check.check_disk import CheckDisk
from utils.platform_util.platform_manager import PlatformManager


import asyncio
import logging
import signal
import sys
import atexit


# Setup logging
logging_config_path = project_root / "configs" / "logging_config.py"
exec(open(logging_config_path).read())
logger = logging.getLogger("MainProcess")

# Initialize PlatformManager for shutdown alerts
platform_manager = PlatformManager()


def send_shutdown_alert(reason="Hệ thống đã dừng"):
    """
    Gửi alert khi hệ thống shutdown

    Args:
        reason: Lý do shutdown
    """
    try:
        logger.warning(f"📤 Gửi alert shutdown: {reason}")
        platform_manager.send_alert(
            api_name="SYSTEM",
            symbol=None,
            overdue_seconds=0,
            allow_delay=0,
            check_frequency=0,
            alert_frequency=0,
            alert_level="error",
            error_message=f"Hệ thống giám sát đã dừng hoạt động - {reason}",
            error_type="SYSTEM",
            source_info={"type": "SYSTEM", "message": "Data monitoring system stopped"},
        )
    except Exception as e:
        logger.error(f"❌ Lỗi gửi shutdown alert: {e}")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("=" * 80)
    logger.info("🛑 Nhận tín hiệu dừng hệ thống - Đang tắt giám sát...")
    logger.info("=" * 80)

    # Gửi alert trước khi tắt
    send_shutdown_alert("Nhận tín hiệu SIGTERM/SIGINT")

    sys.exit(0)


def on_exit():
    """Handler khi chương trình thoát (cả normal và abnormal)"""
    logger.warning("⚠️ Chương trình đang thoát...")
    send_shutdown_alert("Chương trình thoát bất thường")


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register exit handler (bắt cả crash/exception)
atexit.register(on_exit)


async def main():
    """
    Hàm main chạy tất cả các monitors song song

    Chạy đồng thời:
    - API monitoring (check_api)
    - Database monitoring (check_database)
    - Disk monitoring (check_disk) - optional
    """
    logger.info("=" * 80)
    logger.info("🚀 BẮT ĐẦU HỆ THỐNG GIÁM SÁT DỮ LIỆU")
    logger.info("=" * 80)

    # Gửi alert khởi động thành công
    try:
        platform_manager.send_alert(
            api_name="SYSTEM",
            symbol=None,
            overdue_seconds=0,
            allow_delay=0,
            check_frequency=0,
            alert_frequency=0,
            alert_level="info",
            error_message="Hệ thống giám sát đã khởi động thành công",
            error_type="SYSTEM",
            source_info={"type": "SYSTEM", "message": "Data monitoring system started"},
        )
        logger.info("✅ Đã gửi alert khởi động thành công")
    except Exception as e:
        logger.error(f"❌ Lỗi gửi startup alert: {e}")

    # Khởi tạo API checker
    api_checker = CheckAPI()

    # Khởi tạo Database checker
    db_checker = CheckDatabase()

    # Khởi tạo Disk checker (tùy chọn)
    disk_checker = CheckDisk()

    try:
        # Chạy tất cả tasks song song
        await asyncio.gather(
            api_checker.run_api_tasks(),
            db_checker.run_database_tasks(),
            disk_checker.run_disk_tasks(),
        )
    except Exception as e:
        logger.error(f"❌ LỖI NGHIÊM TRỌNG trong main: {e}", exc_info=True)
        # Gửi alert về lỗi nghiêm trọng
        send_shutdown_alert(f"Lỗi nghiêm trọng: {str(e)}")
        raise
    finally:
        logger.info("=" * 80)
        logger.info("🛑 DỪNG HỆ THỐNG GIÁM SÁT DỮ LIỆU")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
