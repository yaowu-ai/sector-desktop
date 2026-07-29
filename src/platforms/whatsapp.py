"""Reserved WhatsApp runner."""
from platforms.base import ReservedPlatformRunner


class WhatsAppRunner(ReservedPlatformRunner):
    def __init__(self):
        super().__init__("whatsapp")
