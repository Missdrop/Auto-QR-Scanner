import sqlite3
import unittest
from unittest.mock import Mock

from src.conversation_search import contact_candidates


class ConversationSearchTest(unittest.TestCase):
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
