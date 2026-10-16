from __future__ import annotations

import logging
import re
from typing import Any

from flask import Flask, jsonify, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from config import Settings, SettingsError
from huggingface_client import HuggingFaceAssistant, MimaServiceError
from memory import ConversationMemory
from prompts import build_messages
from rag import KnowledgeBase, confidence_score
from servicenow import ServiceNowClient, ServiceNowError
from slack_search import fetch_relevant_thread_messages, strip_app_mention
from vendor_status import VendorStatusMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mima")


def _create_bolt_app(
    settings: Settings,
    memory: ConversationMemory,
    knowledge: KnowledgeBase,
    assistant: HuggingFaceAssistant,
    servicenow: ServiceNowClient,
    vendors: VendorStatusMonitor,
) -> App:
    slack_app = App(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    @slack_app.event("app_mention")
    def handle_mention(
        event: dict[str, Any],
        client: Any,
    ) -> None:
        channel = event.get("channel")
        message_ts = event.get("ts")
        user_id = event.get("user", "unknown")
        thread_ts = event.get("thread_ts") or message_ts
        if not channel or not message_ts or not thread_ts:
            logger.warning("Ignoring app_mention without channel/message timestamp")
            return

        question = strip_app_mention(event.get("text", ""))
        if not question:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="Hi! Ask me an incident, service, or runbook question.",
            )
            return

        memory_key = f"{channel}:{thread_ts}"
        history = memory.get_history(memory_key)
        slack_history = fetch_relevant_thread_messages(
            client=client,
            channel=channel,
            thread_ts=thread_ts,
            current_ts=message_ts,
            query=question,
        )
        history.extend(slack_history)

        try:
            response = _answer(
                question=question,
                history=history,
                knowledge=knowledge,
                assistant=assistant,
                servicenow=servicenow,
                vendors=vendors,
            )
            memory.save_exchange(
                thread_key=memory_key,
                user_id=user_id,
                question=question,
                answer=response,
            )
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=response,
                unfurl_links=False,
                unfurl_media=False,
            )
        except (MimaServiceError, ServiceNowError) as error:
            logger.exception("MIMA could not complete the request")
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"I couldn't complete that request: {error}",
            )

    return slack_app


def _answer(
    question: str,
    history: list[dict[str, str]],
    knowledge: KnowledgeBase,
    assistant: HuggingFaceAssistant,
    servicenow: ServiceNowClient,
    vendors: VendorStatusMonitor,
) -> str:
    if _is_vendor_status_request(question, vendors):
        return vendors.format_statuses()

    if _is_incident_creation_request(question):
        incident = servicenow.create_incident(
            short_description=question[:160],
            description=question,
        )
        return (
            f"Created ServiceNow incident *{incident.number}* "
            f"({incident.state}). {incident.url}"
        )

    if _is_incident_lookup_request(question):
        incidents = servicenow.search_incidents(_incident_search_term(question))
        return (
            servicenow.format_incidents(incidents)
            if incidents
            else "ServiceNow returned no matching incidents."
        )

    evidence = knowledge.search(question)
    score = confidence_score(evidence)
    messages = build_messages(
        question=question,
        history=history,
        evidence=evidence,
    )
    answer = assistant.answer(messages)
    confidence_label = (
        "strong" if score >= 70 else "moderate" if score >= 45 else "limited"
    )
    citations = knowledge.format_citations(evidence)
    suffix = f"\n\nConfidence: {score}% ({confidence_label} evidence)."
    if citations:
        suffix += f"\nSources: {citations}"
    return answer.strip() + suffix


def _is_incident_creation_request(question: str) -> bool:
    return bool(
        re.search(
            r"^\s*(?:(?:please|can you|could you|would you|i need you to)\s+)*"
            r"(create|open|raise|log|file)\s+(?:(?:a|an|the)\s+)?"
            r"(?:(?:new|servicenow)\s+)*(incident|ticket)\b",
            question,
            re.IGNORECASE,
        )
    )


def _is_incident_lookup_request(question: str) -> bool:
    if re.search(r"\bINC\d{5,}\b", question, re.IGNORECASE):
        return True
    return bool(
        re.search(r"\b(incidents?|tickets?)\b", question, re.IGNORECASE)
        and re.search(
            r"\b(search|find|look up|lookup|check|show)\b",
            question,
            re.IGNORECASE,
        )
    )


def _incident_search_term(question: str) -> str:
    number = re.search(r"\bINC\d{5,}\b", question, re.IGNORECASE)
    if number:
        return number.group(0).upper()
    return re.sub(
        r"\b(search|find|look up|lookup|check|show|incidents?|tickets?)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    ).strip()


def _is_vendor_status_request(
    question: str,
    vendors: VendorStatusMonitor,
) -> bool:
    if re.search(
        r"\b(vendor|vendors|status page|service status|vendor status)\b",
        question,
        re.IGNORECASE,
    ):
        return True
    mentions_vendor = any(
        name.casefold() in question.casefold() for name in vendors.urls
    )
    return mentions_vendor and bool(
        re.search(r"\b(status|up|down|outage|available|availability|health)\b", question, re.IGNORECASE)
    )


def create_flask_app(settings: Settings | None = None) -> Flask:
    config = settings or Settings.from_env()
    memory = ConversationMemory(config.sqlite_path)
    knowledge = KnowledgeBase(config.knowledge_dir, config.chroma_dir)
    assistant = HuggingFaceAssistant(config.hf_token, config.hf_model)
    servicenow = ServiceNowClient(
        base_url=config.servicenow_url,
        username=config.servicenow_user,
        password=config.servicenow_password,
    )
    vendors = VendorStatusMonitor(
        urls=config.vendor_status_urls,
        poll_seconds=config.vendor_poll_seconds,
    )
    vendors.start()

    bolt_app = _create_bolt_app(
        settings=config,
        memory=memory,
        knowledge=knowledge,
        assistant=assistant,
        servicenow=servicenow,
        vendors=vendors,
    )
    handler = SlackRequestHandler(bolt_app)
    web_app = Flask(__name__)

    @web_app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok", "service": "mima"})

    @web_app.post("/slack/events")
    def slack_events() -> Any:
        return handler.handle(request)

    return web_app


if __name__ == "__main__":
    try:
        application = create_flask_app()
    except SettingsError as error:
        raise SystemExit(str(error)) from error
    application.run(host="0.0.0.0", port=3000)