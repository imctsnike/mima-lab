from __future__ import annotations

import unittest

from rag import RetrievedChunk, _chunk_text, confidence_score


class RagTests(unittest.TestCase):
    def test_confidence_tracks_relevance_and_distinct_sources(self) -> None:
        single = confidence_score([RetrievedChunk("runbook", "incident.txt", 0.8)])
        multiple = confidence_score(
            [
                RetrievedChunk("runbook", "incident.txt", 0.8),
                RetrievedChunk("database", "database.txt", 0.7),
            ]
        )
        self.assertEqual(single, 68)
        self.assertEqual(multiple, 73)
        self.assertEqual(confidence_score([]), 20)

    def test_chunking_respects_limit_and_preserves_all_content(self) -> None:
        text = ("A" * 1250) + "\n\n" + ("second paragraph " * 40)
        chunks = _chunk_text(text, max_chars=500, overlap=50)

        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))
        self.assertTrue(any(chunk.startswith("second paragraph") for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
