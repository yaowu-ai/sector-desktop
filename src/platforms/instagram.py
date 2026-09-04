"""Reserved Instagram runner."""
from platforms.base import ReservedPlatformRunner


class InstagramRunner(ReservedPlatformRunner):
    def __init__(self):
        super().__init__("instagram")


__all__ = ["InstagramRunner"]
