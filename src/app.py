from .history import History
from .scanner import Scanner
from .wechat import WeChat
from .window import Window


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
