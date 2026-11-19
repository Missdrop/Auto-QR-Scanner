import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from browser.scripts import BrowserScripts


class BrowserScriptsTest(unittest.TestCase):
    def test_only_adapter_browser_scripts_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / "example"
            adapter.mkdir()
            script = adapter / "browser.js"
            script.write_text("window.example = true;", encoding="utf-8")
            (adapter / "request.js").write_text("ignored", encoding="utf-8")
            context = Mock()
            BrowserScripts(root).configure(context)
            context.add_init_script.assert_called_once_with(path=script)

    def test_oversized_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / "example"
            adapter.mkdir()
            (adapter / "browser.js").write_bytes(b" " * (256 * 1024 + 1))
            with self.assertRaises(ValueError):
                BrowserScripts(root).configure(Mock())
