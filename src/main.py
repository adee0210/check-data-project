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


import asyncio


async def main():
    """
    Hàm main chạy tất cả các monitors song song

    Chạy đồng thời:
    - API monitoring (check_api)
    - Database monitoring (check_database)
    - Disk monitoring (check_disk) - optional
    """
    # Khởi tạo API checker
    api_checker = CheckAPI()

    # Khởi tạo Database checker
    db_checker = CheckDatabase()

    # Khởi tạo Disk checker (tùy chọn)
    disk_checker = CheckDisk()

    # Chạy tất cả tasks song song
    await asyncio.gather(
        api_checker.run_api_tasks(),
        db_checker.run_database_tasks(),
        disk_checker.run_disk_tasks(),
    )


if __name__ == "__main__":
    asyncio.run(main())
