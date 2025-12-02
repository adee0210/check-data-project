import asyncio


class TaskManager:
    """Quản lý tạo và chạy các task async dùng chung cho nhiều loại kiểm tra"""

    def create_tasks(self, task_func, configs: dict):
        """Tạo danh sách các task từ configs, task_func là hàm async nhận (name, config)"""
        tasks = []
        for name, config in configs.items():
            task = asyncio.create_task(task_func(name, config))
            tasks.append(task)
        return tasks

    async def run_tasks(self, task_func, configs: dict):
        """Khởi tạo và chạy các task với gather, dùng cho mọi loại kiểm tra"""
        tasks = self.create_tasks(task_func, configs)
        await asyncio.gather(*tasks)
