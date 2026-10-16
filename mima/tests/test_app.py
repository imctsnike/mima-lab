from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from app import (
    _incident_search_term,
    _is_incident_creation_request,
    _is_incident_lookup_request,
    _is_vendor_status_request,
    create_flask_app,
)
from config import Settings


class RequestRoutingTests(unittest.TestCase):
    def test_incident_creation_requires_a_direct_action(self) -> None:
        self.assertTrue(_is_incident_creation_request("Please create a new incident"))
        self.assertTrue(_is_incident_creation_request("open ServiceNow ticket for outage"))
        self.assertFalse(_is_incident_creation_request("Should we create an incident?"))
        self.assertFalse(_is_incident_creation_request("How do I create an incident?"))

    def test_incident_lookup_requires_a_lookup_or_ticket_number(self) -> None:
        self.assertTrue(_is_incident_lookup_request("Find incidents for checkout"))
        self.assertTrue(_is_incident_lookup_request("What happened to INC0012345?"))
        self.assertFalse(_is_incident_lookup_request("How should we handle an incident?"))
        self.assertEqual(_incident_search_term("Check INC0012345"), "INC0012345")

    def test_configured_vendor_name_routes_status_question(self) -> None:
        vendors = SimpleNamespace(urls={"Payments": "https://status.example.com"})
        self.assertTrue(_is_vendor_status_request("Is Payments down?", vendors))
        self.assertTrue(_is_vendor_status_request("Show vendor status", vendors))
        self.assertFalse(_is_vendor_status_request("What does Payments provide?", vendors))

    def test_health_endpoint_does_not_require_external_integrations(self) -> None:
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            settings = Settings(
                slack_bot_token="xoxb-test",
                slack_signing_secret="test-secret",
                hf_token="",
                hf_model="test-model",
                servicenow_url="",
                servicenow_user="",
                servicenow_password="",
                sqlite_path=data_dir / "memory.sqlite3",
                chroma_dir=data_dir / "chroma",
                knowledge_dir=data_dir / "knowledge",
                vendor_status_urls={},
                vendor_poll_seconds=300,
            )
            with (
                patch("app.KnowledgeBase", return_value=object()),
                patch("app.VendorStatusMonitor") as monitor,
                patch("app._create_bolt_app", return_value=object()),
                patch("app.SlackRequestHandler"),
            ):
                response = create_flask_app(settings).test_client().get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "service": "mima"})
        monitor.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
