from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class ServiceNowError(RuntimeError):
    pass


@dataclass(frozen=True)
class Incident:
    number: str
    short_description: str
    state: str
    sys_id: str
    url: str


class ServiceNowClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise ServiceNowError(
                "ServiceNow is not configured. Set SERVICENOW_URL, "
                "SERVICENOW_USER, and SERVICENOW_PASSWORD."
            )

    def search_incidents(self, term: str, limit: int = 5) -> list[Incident]:
        self._require_configured()
        safe_term = re.sub(r"[^A-Za-z0-9 _.,:/#-]", " ", term).strip()
        if not safe_term:
            raise ServiceNowError("Provide an incident number or search phrase.")
        if re.fullmatch(r"INC\d{5,}", safe_term, re.IGNORECASE):
            query = f"number={safe_term.upper()}"
        else:
            query = f"short_descriptionLIKE{safe_term}^ORDERBYDESCsys_created_on"
        try:
            response = self.session.get(
                f"{self.base_url}/api/now/table/incident",
                params={
                    "sysparm_query": query,
                    "sysparm_limit": limit,
                    "sysparm_fields": (
                        "number,short_description,state,sys_id"
                    ),
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise ServiceNowError(f"ServiceNow incident search failed: {error}") from error
        except requests.exceptions.JSONDecodeError as error:
            raise ServiceNowError("ServiceNow returned invalid JSON.") from error
        results = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise ServiceNowError("ServiceNow response did not contain an incident list.")
        return [self._incident(record) for record in results if isinstance(record, dict)]

    def create_incident(self, short_description: str, description: str) -> Incident:
        self._require_configured()
        if not short_description.strip() or not description.strip():
            raise ServiceNowError("Incident description must not be empty.")
        try:
            response = self.session.post(
                f"{self.base_url}/api/now/table/incident",
                json={
                    "short_description": short_description[:160],
                    "description": description,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise ServiceNowError(f"ServiceNow incident creation failed: {error}") from error
        except requests.exceptions.JSONDecodeError as error:
            raise ServiceNowError("ServiceNow returned invalid JSON.") from error
        record = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(record, dict):
            raise ServiceNowError("ServiceNow response did not contain the created incident.")
        return self._incident(record)

    def format_incidents(self, incidents: list[Incident]) -> str:
        lines = ["Matching ServiceNow incidents:"]
        for incident in incidents:
            lines.append(
                f"- {incident.number} ({incident.state}): "
                f"{incident.short_description} - {incident.url}"
            )
        return "\n".join(lines)

    def _incident(self, record: dict[str, Any]) -> Incident:
        number = str(record.get("number", "Unknown"))
        sys_id = str(record.get("sys_id", ""))
        url = (
            f"{self.base_url}/incident.do?sys_id={quote(sys_id)}"
            if sys_id
            else self.base_url
        )
        return Incident(
            number=number,
            short_description=str(record.get("short_description", "No description")),
            state=str(record.get("state", "unknown")),
            sys_id=sys_id,
            url=url,
        )