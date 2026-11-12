import argparse
import json
import subprocess
from pathlib import Path
from time import sleep
from urllib.request import ProxyHandler, Request, build_opener

from .ams import NoRedirect
from .login_storage import LoginStorage
from .runtime import Chromium


class Login:
    """
    Open ordinary Chrome without extensions, injected scripts or debugging flags.
    """

    def __init__(self, directory: Path, port: int = 52841) -> None:
        self._directory = directory
        self._port = port
        self._key = (directory / "login.key").read_text(encoding="ascii").strip()
        self._last: dict[str, str] | None = None
        self._http = build_opener(ProxyHandler({}), NoRedirect())
        self._storage = LoginStorage(directory / "chromium")

    @staticmethod
    def executable() -> Path:
        return Chromium().executable()

    def send(self, payload: dict[str, str]) -> None:
        request = Request(
            f"http://127.0.0.1:{self._port}/event",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + self._key,
                "Content-Type": "application/json",
            },
        )
        with self._http.open(request, timeout=2):
            pass

    def inspect(self) -> None:
        session = self._storage.session()
        if session and session != self._last:
            self.send({"event": "session", **session})
            self._last = session
        elif session is None and self._last is not None:
            self.send({"event": "logout"})
            self._last = None

    def run(self) -> None:
        profile = self._directory / "chromium"
        profile.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            [
                str(self.executable()),
                "--app=https://ams.xjtlu.edu.cn/studentpc/",
                "--user-data-dir=" + str(profile),
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            while True:
                try:
                    self.inspect()
                except Exception:
                    # Chrome may be rotating a log; retry a fresh snapshot.
                    pass
                if process.poll() is not None:
                    self.inspect()
                    break
                sleep(2)
        finally:
            if process.poll() is not None:
                process.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    arguments = parser.parse_args()
    login = Login(arguments.data.resolve())
    try:
        login.run()
    except Exception:
        login.send({"event": "login-unavailable"})


if __name__ == "__main__":
    main()
