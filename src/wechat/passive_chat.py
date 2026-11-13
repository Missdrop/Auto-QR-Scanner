from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
import uiautomation
import win32gui

from wechat.qt_access import QtAccess


class Photo:
    """
    Inspect an image bubble without constructing backend sender objects.
    """

    def __init__(
        self,
        control: Any,
        client: Any,
        directory: Path,
        notify: Callable[[str], None] | None = None,
    ) -> None:
        self.control = control
        self.id = str(control.GetRuntimeId())
        self.type = "image" if control.Name in {"图片", "[图片]", "Image"} else "other"
        self._client = client
        self._directory = directory
        self._path: Path | None = None
        self._bounds: tuple[int, int, int, int] | None = None
        self._attr = "unknown"
        self._notify = notify

    @staticmethod
    def locate(image: np.ndarray) -> tuple[int, int, int, int]:
        height, width = image.shape[:2]
        # A bubble row has a flat background and a much larger photo than avatar.
        pixels = image.reshape(-1, 3)
        colors, counts = np.unique(pixels[::4], axis=0, return_counts=True)
        background = colors[counts.argmax()].astype(np.int16)
        difference = np.abs(image.astype(np.int16) - background).max(axis=2)
        mask = (difference > 24).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        _, _, statistics, _ = cv2.connectedComponentsWithStats(mask)
        candidates = [
            (int(row[0]), int(row[1]), int(row[2]), int(row[3]))
            for row in statistics[1:]
            if row[2] >= 40
            and row[3] >= 70
            and row[4] >= 1000
            and row[2] < width * 0.9
            and row[3] <= height
        ]
        if not candidates:
            raise ValueError("Cannot locate the image bubble")
        return max(candidates, key=lambda bounds: bounds[2] * bounds[3])

    @property
    def attr(self) -> str:
        if self._path is None:
            self._directory.mkdir(parents=True, exist_ok=True)
            self._path = self._directory / (uuid4().hex + ".png")
            if not self.control.CaptureToImage(str(self._path)):
                raise ValueError("Cannot capture the visible image bubble")
            content = np.fromfile(self._path, dtype=np.uint8)
            image = cv2.imdecode(content, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Cannot read the image bubble")
            self._bounds = self.locate(image)
            left, top, width, height = self._bounds
            center = left + width / 2
            if abs(center - image.shape[1] / 2) < 20:
                raise ValueError("Cannot determine the image direction")
            self._attr = "friend" if center < image.shape[1] / 2 else "self"
            preview = image[top : top + height, left : left + width]
            encoded, content = cv2.imencode(".png", preview)
            if not encoded:
                raise ValueError("Cannot save the image preview")
            content.tofile(self._path)
        return self._attr

    def download(self) -> Path:
        if self._bounds is None or self._path is None:
            raise ValueError("Inspect the image direction before opening it")
        from wxauto4.ui.component import WeChatImage

        left, top, width, height = self._bounds
        viewer = None
        try:
            self.control.DoubleClick(x=left + width // 2, y=top + height // 2)
            viewer = WeChatImage(self._client.ChatBox)
            return Path(viewer.save(dir_path=str(self._directory), timeout=5))
        except Exception:
            if self._notify is not None:
                self._notify("Full image unavailable; scanning the visible preview")
            return self._path
        finally:
            if viewer is not None:
                viewer.close()


class PassiveChat:
    """
    Read titles and message identifiers without opening profiles or context menus.
    """

    def __init__(
        self,
        client: Any,
        directory: Path,
        notify: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._directory = directory
        self._notify = notify
        self._window, _ = QtAccess._window()
        root = uiautomation.ControlFromHandle(self._window)
        if root is None:
            raise ValueError("Cannot inspect the WeChat main window")
        self._messages = root.ListControl(AutomationId="chat_message_list")
        self._title = root.TextControl(
            AutomationId="content_view.top_content_view.title_h_view.left_v_view."
            "left_content_v_view.left_ui_.big_title_line_h_view.current_chat_name_label"
        )
        if not self._messages.Exists(1) or not self._title.Exists(1):
            raise ValueError("The active conversation controls are unavailable")

    def name(self) -> str:
        return self._title.Name

    def is_foreground(self) -> bool:
        return win32gui.GetForegroundWindow() == self._window

    def messages(self) -> list[Photo]:
        return [
            Photo(control, self._client, self._directory, self._notify)
            for control in self._messages.GetChildren()
        ]
