from __future__ import annotations

import unittest

from vendor_status import _parse_status


class VendorStatusTests(unittest.TestCase):
    def test_parses_statuspage_response(self) -> None:
        self.assertEqual(
            _parse_status(
                {
                    "status": {
                        "indicator": "minor",
                        "description": "Partial outage",
                    }
                }
            ),
            ("degraded", "Partial outage"),
        )

    def test_parses_simple_healthy_response(self) -> None:
        self.assertEqual(_parse_status({"state": "healthy"}), ("operational", "healthy"))


if __name__ == "__main__":
    unittest.main()
