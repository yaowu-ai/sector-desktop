"""Base classes for platform-specific runners."""


class PlatformRunner:
    platform = ""
    executable = False
    reserved_reason = "platform runner is reserved"

    def can_execute(self):
        return bool(self.executable)

    def run_session(self, account, config, conn):
        raise NotImplementedError

    def skip_message(self, account):
        return (
            f"[skip] account {account.get('id')} platform={self.platform} is reserved; "
            f"{self.reserved_reason}"
        )


class ReservedPlatformRunner(PlatformRunner):
    executable = False

    def __init__(self, platform, reason="not adapted for automatic execution in V1"):
        self.platform = platform
        self.reserved_reason = reason
