from __future__ import annotations

import unittest

from slack_search import strip_app_mention


class SlackMentionTests(unittest.TestCase):
    def test_removes_app_and_special_mentions(self) -> None:
        self.assertEqual(
            strip_app_mention("<@U123> check <@U456> and <!here> status"),
            "check and status",
        )


if __name__ == "__main__":
    unittest.main()
