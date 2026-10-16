from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory import ConversationMemory


class ConversationMemoryTests(unittest.TestCase):
    def test_exchange_is_saved_and_returned_in_chronological_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = ConversationMemory(Path(directory) / "memory.sqlite3")
            memory.save_exchange("C1:123.4", "U1", "What failed?", "Database saturation.")
            memory.save_exchange("C1:123.4", "U2", "Next step?", "Check connections.")
            memory.save_exchange("C1:456.7", "U1", "Other thread", "Separate context.")

            self.assertEqual(
                memory.get_history("C1:123.4"),
                [
                    {"role": "user", "content": "What failed?"},
                    {"role": "assistant", "content": "Database saturation."},
                    {"role": "user", "content": "Next step?"},
                    {"role": "assistant", "content": "Check connections."},
                ],
            )
            self.assertEqual(
                memory.get_history("C1:456.7"),
                [
                    {"role": "user", "content": "Other thread"},
                    {"role": "assistant", "content": "Separate context."},
                ],
            )

    def test_history_is_capped_to_most_recent_messages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = ConversationMemory(Path(directory) / "memory.sqlite3", history_limit=2)
            memory.save_exchange("thread", "user", "first", "answer one")
            memory.save_exchange("thread", "user", "second", "answer two")

            self.assertEqual(
                memory.get_history("thread"),
                [
                    {"role": "user", "content": "second"},
                    {"role": "assistant", "content": "answer two"},
                ],
            )


if __name__ == "__main__":
    unittest.main()
