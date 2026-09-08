class BridgeError(Exception):
    """Ko'prik xizmati bilan bog'liq har qanday xato uchun asosiy klass."""


class ModuleNotConfigured(BridgeError):
    """Maqsad modul (masalan Ombor) uchun ulanish sozlanmagan (base_url yo'q)."""


class ModuleHTTPError(BridgeError):
    """Maqsad modul HTTP xato bilan javob berdi (4xx/5xx)."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"{status_code}: {body}")


class ModuleUnreachable(BridgeError):
    """Tarmoq darajasida ulanib bo'lmadi (timeout, DNS, connection refused)."""
