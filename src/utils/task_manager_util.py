import asyncio


class TaskManager:
    """Quản lý tạo và chạy các task async dùng chung cho nhiều loại kiểm tra"""

    def create_tasks(self, task_func, configs: dict):
        """
        Tạo danh sách các task từ configs

        Args:
            task_func: Hàm async nhận (name, config, symbol)
            configs: Dict chứa cấu hình các tasks

        Returns:
            List of asyncio tasks
        """
        tasks = []
        for name, config in configs.items():
            symbols = config.get("symbols")

            if symbols:
                # Nếu có symbols, tạo task cho mỗi symbol
                for symbol in symbols:
                    task = asyncio.create_task(task_func(name, config, symbol))
                    tasks.append(task)
            else:
                # Không có symbols, tạo task bình thường
                task = asyncio.create_task(task_func(name, config, None))
                tasks.append(task)
        return tasks

    async def run_tasks(self, task_func, configs: dict):
        """
        Khởi tạo và chạy các task với gather

        Args:
            task_func: Hàm async nhận (name, config, symbol)
            configs: Dict chứa cấu hình các tasks
        """
        tasks = self.create_tasks(task_func, configs)
        await asyncio.gather(*tasks)
