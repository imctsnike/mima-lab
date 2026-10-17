# MIMA - Major Incident Management Assistant

MIMA is a Python Slack assistant for incident response. It answers app mentions
using a Hugging Face chat model grounded in local runbooks, keeps per-thread
conversation memory in SQLite, searches or creates ServiceNow incidents on
request, and monitors configured vendor status endpoints.

## Features

- Slack Bolt `app_mention` event handling with replies kept in the originating
  Slack thread.
- Hugging Face Inference API text generation with `google/flan-t5-large`.
- Persistent ChromaDB retrieval over `.txt` documents under `knowledge/`.
- SQLite conversation history, separated by channel and thread.
- Optional ServiceNow incident search and explicitly requested incident
  creation.
- Background vendor status polling for Statuspage v2 and compatible JSON APIs.
- Evidence-based confidence score. This estimates retrieval grounding; it is
  not a calibrated probability that the model's answer is correct.
- Flask `/health` and `/slack/events` endpoints, Docker image, and Compose
  configuration.

## Configure Slack

Create a Slack app and enable **Event Subscriptions**. Set the request URL to
`https://<your-public-host>/slack/events`, then subscribe the bot to
`app_mention`. Install the app and invite it to the channels where it should
respond.

Add these bot token scopes before installing/reinstalling:

- `app_mentions:read`
- `chat:write`
- `channels:history` and `groups:history` to use related messages already in a
  Slack thread. Thread-context lookup is best-effort; MIMA logs and continues
  with SQLite memory if Slack does not grant access.

Copy `.env.example` to `.env` and set `SLACK_BOT_TOKEN` and
`SLACK_SIGNING_SECRET`. Do not commit `.env`.

## Deploy on Render

Render does not automatically load your local `.env` file. In the Render
service dashboard, open **Environment** and add `SLACK_BOT_TOKEN` and
`SLACK_SIGNING_SECRET` with the values from your Slack app, then save and
redeploy. Both are required for the service to start; the other integrations
are optional.

## Configure integrations

| Variable | Required | Purpose |
| --- | --- | --- |
| `HF_TOKEN` | For AI answers | Hugging Face user access token |
| `HF_MODEL` | No | Hugging Face model ID; defaults to `google/flan-t5-large` |
| `SERVICENOW_URL` | For ServiceNow | Instance base URL, e.g. `https://example.service-now.com` |
| `SERVICENOW_USER` | For ServiceNow | Service account username |
| `SERVICENOW_PASSWORD` | For ServiceNow | Service account password |
| `VENDOR_STATUS_URLS` | No | JSON object mapping vendor names to status JSON URLs |
| `VENDOR_POLL_SECONDS` | No | Poll interval in seconds (minimum 30; default 300) |
| `MIMA_DATA_DIR` | No | SQLite and ChromaDB storage directory |

ServiceNow uses the Table API and Basic Authentication. Give the service account
only the incident read/create permissions it needs. Mention a ticket number
(such as `INC0012345`) or describe an incident to search. MIMA only creates an
incident when directly asked to create, open, raise, log, or file one.

Vendor status endpoints are checked periodically. Statuspage v2 JSON and
compatible payloads with `status.indicator` or `status`/`state` fields are
supported. Ask MIMA for the "vendor status" to see the latest poll results.

## Run locally

Python 3.12 or newer is recommended.

```bash
cd mima
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Slack and Hugging Face credentials.
python app.py
```

Expose port 3000 through HTTPS for Slack's Events API and use
`https://<host>/slack/events` as the request URL. Local run data is written to
`data/`; add `.txt` files to `knowledge/` and restart to index them.

## Run with Docker

```bash
cp .env.example .env
# Edit .env.
docker compose up --build -d
```

Compose keeps SQLite and ChromaDB data in the `mima-data` named volume. Publish
the container behind an HTTPS reverse proxy for Slack event delivery.

## Confidence and operations

The displayed percentage is a retrieval-grounding estimate derived from the
best Chroma cosine match and the number of distinct supporting documents.
Answers without matching local evidence receive a low score. Review source
citations and verify incident-impacting recommendations before acting. Logs go
to standard output; `/health` reports process health, not integration health.

## Tests

```bash
python -m unittest discover -s tests -v
```
