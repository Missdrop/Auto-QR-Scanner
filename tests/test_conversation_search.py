import sqlite3
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from src.conversation_search import ConversationSearch, contact_candidates


class ConversationSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_crashed_lookup_reports_failure_and_next_query_restarts_it(self):
        search = ConversationSearch(Path("unused"))
        old = Mock()
        old.is_alive.return_value = False
        search._process = old
        search._requests, search._results = Mock(), Mock()
        failures = []
        search.failed.connect(failures.append)
        search._receive()
        self.assertEqual(len(failures), 1)
        old.terminate.assert_not_called()
        old.close.assert_called_once()
        context = Mock()
        try:
            with patch(
                "src.conversation_search.multiprocessing.get_context",
                return_value=context,
            ):
                search.request("24")
            context.Process.return_value.start.assert_called_once()
        finally:
            search.close()

    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE contact (username TEXT, nick_name TEXT, remark TEXT)"
        )
        self.database = Mock()
        self.database._contact_conn.return_value = self.connection

    def tearDown(self) -> None:
        self.connection.close()

    def test_prefix_filter_precedes_the_result_limit(self) -> None:
        self.connection.executemany(
            "INSERT INTO contact VALUES (?, ?, '')",
            [(str(i), f"Other ICS {i}") for i in range(60)]
            + [("target", "ICS Group"), ("remark", "ICS Hidden")],
        )
        self.connection.execute(
            "UPDATE contact SET remark = 'Different name' WHERE username = 'remark'"
        )
        rows = contact_candidates(self.database, "ic")
        self.assertEqual([row["username"] for row in rows], ["target"])
        self.database.search_contact.assert_not_called()

    def test_chinese_prefix_and_wildcards_are_literal(self) -> None:
        self.connection.executemany(
            "INSERT INTO contact VALUES (?, ?, '')",
            [("one", "大群一"), ("two", "专业大群"), ("three", "大%群")],
        )
        rows = contact_candidates(self.database, "大%")
        self.assertEqual([row["username"] for row in rows], ["three"])

    def test_missing_contact_database_is_reported(self) -> None:
        self.database._contact_conn.return_value = None
        with self.assertRaises(RuntimeError):
            contact_candidates(self.database, "Group")
