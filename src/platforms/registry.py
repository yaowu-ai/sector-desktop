"""Platform runner registry."""
from platform_config import normalize_platform
from platforms.douyin import DouyinRunner
from platforms.instagram import InstagramRunner
from platforms.tiktok import TikTokRunner
from platforms.whatsapp import WhatsAppRunner

_RUNNERS = {
    "tiktok": TikTokRunner(),
    "instagram": InstagramRunner(),
    "whatsapp": WhatsAppRunner(),
    "douyin": DouyinRunner(),
}


def get_runner(platform):
    platform = normalize_platform(platform)
    return _RUNNERS[platform]


def registered_platforms():
    return sorted(_RUNNERS)


def executable_platforms():
    return sorted(platform for platform, runner in _RUNNERS.items() if runner.can_execute())
