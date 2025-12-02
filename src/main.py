import sys
from pathlib import Path


def find_project_root(current_file, marker="requirements.txt"):
    current_path = Path(current_file).resolve()
    for parent in current_path.parents:
        if (parent / marker).exists():
            return parent
    return current_path.parent


project_root = find_project_root(__file__, marker="requirements.txt")
sys.path.insert(0, str(project_root))


from check.check_api import CheckAPI
from check.check_database import CheckDatabase


import asyncio


async def main():
    # Chạy API checks
    api_checker = CheckAPI()

    # Chạy Database checks
    db_checker = CheckDatabase()

    # Chạy song song cả API và Database checks
    await asyncio.gather(api_checker.run_api_tasks(), db_checker.run_database_tasks())


asyncio.run(main())
