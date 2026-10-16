from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class ConversationMemory:
    """Persist short Slack thread exchanges in a local SQLite database."""

    def __init__(self, path: Path, history_limit: int = 8) -> None:
        self.path = path
        self.history_limit = history_limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_key TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_thread "
                "ON messages(thread_key, id)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def get_history(self, thread_key: str) -> list[dict[str, str]]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE thread_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (thread_key, self.history_limit),
            ).fetchall()
        return [
            {"role": row["role"], "content": row["content"]}
            for row in reversed(rows)
        ]

    def save_exchange(
        self,
        thread_key: str,
        user_id: str,
        question: str,
        answer: str,
    ) -> None:
        if not thread_key or not user_id or not question.strip() or not answer.strip():
            raise ValueError("Thread, user, question, and answer must be non-empty.")
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO messages (thread_key, user_id, role, content)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (thread_key, user_id, "user", question.strip()),
                    (thread_key, user_id, "assistant", answer.strip()),
                ],
            )