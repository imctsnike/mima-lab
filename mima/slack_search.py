from __future__ import annotations

import logging
import re
from typing import Any

from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


def strip_app_mention(text: str) -> str:
    cleaned = re.sub(r"<@[A-Z0-9]+>", " ", text)
    cleaned = re.sub(r"<!subteam\^[A-Z0-9]+(?:\|[^>]+)?>", " ", cleaned)
    cleaned = re.sub(r"<!(?:here|channel|everyone)>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def fetch_relevant_thread_messages(
    client: Any,
    channel: str,
    thread_ts: str,
    current_ts: str,
    query: str,
    limit: int = 4,
) -> list[dict[str, str]]:
    try:
        response = client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=50,
        )
    except SlackApiError:
        logger.exception(
            "Slack thread history is unavailable; continuing without it "
            "(channel=%s, thread_ts=%s)",
            channel,
            thread_ts,
        )
        return []

    terms = {word.casefold() for word in re.findall(r"\w{3,}", query)}
    ranked: list[tuple[int, int, dict[str, str]]] = []
    for position, message in enumerate(response.get("messages", [])):
        if message.get("ts") == current_ts or message.get("bot_id"):
            continue
        text = str(message.get("text", "")).strip()
        if not text:
            continue
        score = len(terms.intersection(word.casefold() for word in re.findall(r"\w{3,}", text)))
        if score:
            ranked.append((score, position, {"role": "user", "content": text}))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(ranked[:limit], key=lambda item: item[1])
    return [message for _, _, message in selected]