"""Reserved Douyin runner."""
from platforms.base import ReservedPlatformRunner


class DouyinRunner(ReservedPlatformRunner):
    def __init__(self):
        super().__init__("douyin")
