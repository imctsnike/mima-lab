from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VendorStatus:
    name: str
    status: str
    details: str
    checked_at: str


class VendorStatusMonitor:
    def __init__(
        self,
        urls: dict[str, str],
        poll_seconds: int = 300,
        timeout: float = 10,
    ) -> None:
        self.urls = urls
        self.poll_seconds = poll_seconds
        self.timeout = timeout
        self._statuses: dict[str, VendorStatus] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.urls or (self._thread and self._thread.is_alive()):
            return
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="mima-vendor-status",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.timeout + 1)

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self.check_now()
            self._stop_event.wait(self.poll_seconds)

    def check_now(self) -> list[VendorStatus]:
        results = [self._check_vendor(name, url) for name, url in self.urls.items()]
        with self._lock:
            self._statuses = {status.name: status for status in results}
        return results

    def _check_vendor(self, name: str, url: str) -> VendorStatus:
        checked_at = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            response = requests.get(url, timeout=self.timeout)
        except requests.RequestException as error:
            logger.warning("Vendor status request failed for %s: %s", name, error)
            return VendorStatus(name, "unreachable", str(error), checked_at)

        if not 200 <= response.status_code < 300:
            return VendorStatus(
                name,
                "unavailable",
                f"Status endpoint returned HTTP {response.status_code}.",
                checked_at,
            )
        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError:
            logger.warning("Vendor status endpoint for %s returned invalid JSON", name)
            return VendorStatus(
                name,
                "unknown",
                "Status endpoint returned a successful response without valid JSON.",
                checked_at,
            )
        status, details = _parse_status(payload)
        return VendorStatus(name, status, details, checked_at)

    def get_statuses(self) -> list[VendorStatus]:
        with self._lock:
            return sorted(self._statuses.values(), key=lambda item: item.name.casefold())

    def format_statuses(self) -> str:
        statuses = self.get_statuses()
        if not self.urls:
            return (
                "No vendor status endpoints are configured. Set "
                "VENDOR_STATUS_URLS to a JSON object of vendor names and status URLs."
            )
        if not statuses:
            return "Vendor status checks are starting; no results are available yet."
        lines = ["*Vendor status (latest check):*"]
        lines.extend(
            f"- *{item.name}:* {item.status} - {item.details} "
            f"(checked {item.checked_at} UTC)"
            for item in statuses
        )
        return "\n".join(lines)


def _parse_status(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        return "unknown", "Status endpoint returned an unexpected response."
    raw = payload.get("status", payload.get("state", "unknown"))
    if isinstance(raw, dict):
        status = str(raw.get("indicator", raw.get("state", "unknown"))).casefold()
        details = str(raw.get("description", raw.get("message", status)))
    else:
        status = str(raw).casefold()
        details = str(payload.get("description", status))
    if status in {"operational", "ok", "up", "healthy", "none"}:
        return "operational", details
    if status in {"minor", "major", "critical", "degraded", "maintenance", "down"}:
        return "degraded", details
    if status in {"unknown", ""}:
        return "unknown", details
    return status, details