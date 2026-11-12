import os
import webbrowser
from pathlib import Path


class Browser:
    """
    Open AMS in the installed Chrome profile used by the companion extension.
    """

    @staticmethod
    def executable() -> Path | None:
        for location in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            directory = os.environ.get(location)
            if directory:
                path = Path(directory) / "Google/Chrome/Application/chrome.exe"
                if path.is_file():
                    return path
        return None

    def open(self, url: str) -> bool:
        executable = self.executable()
        if executable is not None:
            # Pass the complete hash URL as one argument, without a shell handler.
            return webbrowser.BackgroundBrowser(str(executable)).open(url, new=2)
        return webbrowser.open(url, new=2)
