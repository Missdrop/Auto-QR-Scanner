import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .history import History
from .image_processor import ImageProcessor
from .message import ImageMessage
from .scanner import Scanner


def main() -> int:
    """
    Launch the desktop or decode local images without opening any links.
    """
    parser = argparse.ArgumentParser(description="Scan QR codes from group images")
    parser.add_argument(
        "--scan", nargs="+", type=Path, help="Decode local images as JSON"
    )
    parser.add_argument(
        "--data", type=Path, default=Path("data"), help="Local data directory"
    )
    arguments = parser.parse_args()
    scanner = Scanner(ImageProcessor())

    if arguments.scan:
        return scan_files(scanner, arguments.scan)

    # Import desktop modules only when a window is requested.
    from PySide6.QtWidgets import QApplication

    from .app import App
    from .wechat import WeChat
    from .window import Window

    application = QApplication(sys.argv[:1])
    window = Window()
    data_directory = arguments.data.resolve()
    controller = App(
        WeChat(data_directory / "images"),
        scanner,
        History(data_directory / "history.sqlite3"),
        window,
        data_directory / "browser",
    )
    application.aboutToQuit.connect(controller.close)
    window.show()
    return application.exec()


def scan_files(scanner: Scanner, paths: list[Path]) -> int:
    failures = 0
    for path in paths:
        message = ImageMessage(
            uuid4().hex,
            "Local image",
            path.resolve(),
            datetime.now().astimezone(),
        )
        result = scanner.scan(message)
        print(
            json.dumps(
                {
                    "image": str(path),
                    "status": result.status(),
                    "codes": [code.text for code in result.codes],
                    "elapsed_ms": round(result.elapsed_ms, 1),
                    "error": result.error,
                },
                ensure_ascii=True,
            )
        )
        if not result.codes:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
