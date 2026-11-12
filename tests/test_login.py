import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.login import Login


class LoginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "login.key").write_text("local-key", encoding="ascii")
        self.login = Login(root)
        self.login._storage = Mock()

    def test_session_is_synchronized_once_and_logout_is_reported(self) -> None:
        self.login._storage.session.return_value = {
            "userId": "student",
            "token": "secret",
        }
        with patch.object(self.login, "send") as send:
            self.login.inspect()
            self.login.inspect()
            send.assert_called_once_with(
                {"event": "session", "userId": "student", "token": "secret"}
            )
            self.login._storage.session.return_value = None
            self.login.inspect()
            send.assert_called_with({"event": "logout"})
