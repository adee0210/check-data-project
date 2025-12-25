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


logging_config_path = project_root / "configs" / "logging_config.py"
exec(open(logging_config_path).read())
logger = logging.getLogger("MainProcess")

platform_manager = PlatformManager()

# Flag để tránh gửi alert duplicate khi shutdown bình thường
_shutdown_handled = False


def send_shutdown_alert(reason="Hệ thống đã dừng", alert_level="info"):
    """
    Gửi alert khi hệ thống shutdown

    Args:
        reason: Lý do shutdown
        alert_level: Mức độ alert ("info" cho shutdown bình thường, "error" cho lỗi)
    """
    global _shutdown_handled
    if _shutdown_handled:
        return

    try:
        log_func = logger.info if alert_level == "info" else logger.warning
        log_func(f"Gửi alert shutdown: {reason}")
        platform_manager.send_alert(
            api_name="SYSTEM",
            symbol=None,
            overdue_seconds=0,
            allow_delay=0,
            check_frequency=0,
            alert_frequency=0,
            alert_level=alert_level,
            error_message=f"Hệ thống giám sát đã dừng hoạt động - {reason}",
            error_type="SYSTEM",
            source_info={"type": "SYSTEM", "message": "Data monitoring system stopped"},
        )
        _shutdown_handled = True
    except Exception as e:
        logger.error(f"Lỗi gửi shutdown alert: {e}")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_handled
    logger.info("Nhận tín hiệu dừng hệ thống - Đang tắt giám sát...")

    # Gửi alert INFO cho shutdown có kiểm soát
    send_shutdown_alert("Nhận tín hiệu SIGTERM/SIGINT", alert_level="info")
    _shutdown_handled = True

    sys.exit(0)


def on_exit():
    """Handler khi chương trình thoát bất thường (crash/exception)"""
    global _shutdown_handled
    # Chỉ gửi alert nếu chưa được xử lý bởi signal handler
    if not _shutdown_handled:
        logger.warning("Chương trình thoát bất thường...")
        send_shutdown_alert("Chương trình thoát bất thường", alert_level="error")


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
            error_message="Check Data đã khởi động",
            error_type="SYSTEM",
            source_info={"type": "SYSTEM", "message": "Data monitoring system started"},
        )
        logger.info(" Đã gửi alert")
    except Exception as e:
        logger.error(f"Lỗi gửi startup alert: {e}")

    # Khởi tạo API checker
    api_checker = CheckAPI()

    # Khởi tạo Database checker
    db_checker = CheckDatabase()

    # Khởi tạo Disk checker
    disk_checker = CheckDisk()

    try:
        # Chạy tất cả tasks song song
        await asyncio.gather(
            api_checker.run_api_tasks(),
            db_checker.run_database_tasks(),
            disk_checker.run_disk_tasks(),
        )
    except Exception as e:
        logger.error(f"LỖI NGHIÊM TRỌNG trong main: {e}", exc_info=True)
        # Gửi alert về lỗi
        send_shutdown_alert(f"Lỗi nghiêm trọng: {str(e)}", alert_level="error")
        raise
    finally:
        logger.info("DỪNG CHECK DATA")


if __name__ == "__main__":
    asyncio.run(main())
