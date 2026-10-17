from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_signing_secret: str
    hf_token: str
    hf_model: str
    servicenow_url: str
    servicenow_user: str
    servicenow_password: str
    sqlite_path: Path
    chroma_dir: Path
    knowledge_dir: Path
    vendor_status_urls: dict[str, str]
    vendor_poll_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
        slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET", "").strip()
        missing = [
            name
            for name, value in (
                ("SLACK_BOT_TOKEN", slack_bot_token),
                ("SLACK_SIGNING_SECRET", slack_signing_secret),
            )
            if not value
        ]
        if missing:
            raise SettingsError(
                "Missing required configuration: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and set the Slack values."
            )

        data_dir = Path(os.getenv("MIMA_DATA_DIR", PROJECT_DIR / "data")).expanduser()
        try:
            poll_seconds = int(os.getenv("VENDOR_POLL_SECONDS", "300"))
        except ValueError as error:
            raise SettingsError("VENDOR_POLL_SECONDS must be an integer.") from error
        if poll_seconds < 30:
            raise SettingsError("VENDOR_POLL_SECONDS must be at least 30.")

        vendor_urls = _parse_vendor_urls(os.getenv("VENDOR_STATUS_URLS", "{}"))
        return cls(
            slack_bot_token=slack_bot_token,
            slack_signing_secret=slack_signing_secret,
            hf_token=os.getenv("HF_TOKEN", "").strip(),
            hf_model=os.getenv(
                "HF_MODEL",
                "google/flan-t5-large",
            ).strip(),
            servicenow_url=os.getenv("SERVICENOW_URL", "").strip().rstrip("/"),
            servicenow_user=os.getenv("SERVICENOW_USER", "").strip(),
            servicenow_password=os.getenv("SERVICENOW_PASSWORD", ""),
            sqlite_path=data_dir / "memory.sqlite3",
            chroma_dir=data_dir / "chroma",
            knowledge_dir=Path(
                os.getenv("MIMA_KNOWLEDGE_DIR", PROJECT_DIR / "knowledge")
            ).expanduser(),
            vendor_status_urls=vendor_urls,
            vendor_poll_seconds=poll_seconds,
        )


def _parse_vendor_urls(value: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise SettingsError("VENDOR_STATUS_URLS must be a JSON object.") from error
    if not isinstance(parsed, dict):
        raise SettingsError("VENDOR_STATUS_URLS must be a JSON object.")
    result: dict[str, str] = {}
    for name, url in parsed.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str):
            raise SettingsError(
                "VENDOR_STATUS_URLS must map non-empty vendor names to URLs."
            )
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise SettingsError(f"Invalid status URL for vendor {name!r}.")
        result[name.strip()] = url
    return result
