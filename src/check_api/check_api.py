import os
import json


class CheckAPI:
    def __init__(self):

        self.config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "configs",
            "config.json",
        )
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
