from __future__ import annotations

import unittest
from unittest.mock import Mock

from servicenow import ServiceNowClient


class ServiceNowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ServiceNowClient(
            base_url="https://instance.example.com/",
            username="mima",
            password="test-password",
        )

    def test_search_by_number_returns_incident_and_permalink(self) -> None:
        response = Mock()
        response.json.return_value = {
            "result": [
                {
                    "number": "INC0012345",
                    "short_description": "Checkout failures",
                    "state": "In Progress",
                    "sys_id": "abc123",
                }
            ]
        }
        self.client.session.get = Mock(return_value=response)

        incidents = self.client.search_incidents("INC0012345")

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].number, "INC0012345")
        self.assertEqual(
            incidents[0].url,
            "https://instance.example.com/incident.do?sys_id=abc123",
        )
        self.assertEqual(
            self.client.session.get.call_args.kwargs["params"]["sysparm_query"],
            "number=INC0012345",
        )

    def test_create_posts_only_the_requested_incident_fields(self) -> None:
        response = Mock()
        response.json.return_value = {
            "result": {
                "number": "INC0012346",
                "short_description": "Payment API unavailable",
                "state": "New",
                "sys_id": "def456",
            }
        }
        self.client.session.post = Mock(return_value=response)

        incident = self.client.create_incident(
            "Payment API unavailable",
            "Customers cannot complete checkout.",
        )

        self.assertEqual(incident.number, "INC0012346")
        self.assertEqual(
            self.client.session.post.call_args.kwargs["json"],
            {
                "short_description": "Payment API unavailable",
                "description": "Customers cannot complete checkout.",
            },
        )


if __name__ == "__main__":
    unittest.main()
