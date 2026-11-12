from auto_qr_scanner.history import History
from auto_qr_scanner.scanner import Scanner
from auto_qr_scanner.wechat import WeChat
from auto_qr_scanner.window import Window


class App:
    """
    Organize monitoring, scanning, history and desktop interaction.

    Startup, background processing and shutdown are not implemented yet.
    """

    def __init__(
        self, wechat: WeChat, scanner: Scanner, history: History, window: Window
    ) -> None:
        # Delegate concrete work to the objects responsible for it.
        self._wechat = wechat
        self._scanner = scanner
        self._history = history
        self._window = window
