# Elias Telegram Bot

Elias is a fictional AI character: a 25-year-old woman from Massachusetts, USA,
with a warm, playful, lightly flirty conversational style. She matches the user's
language, keeps replies short, and is honest about being AI.

## Run locally

Requires Python 3.12+. Install `pip install -r requirements.txt`, set
`TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` in your process environment, then run
`python bot.py`. `.env.example` lists names only; the app does not automatically
load .env files. Never commit keys. Optional `OPENAI_MODEL` defaults to `gpt-4.1-mini`.

## Railway

Connect this GitHub repository to the existing Railway service. Railway builds
the Dockerfile and runs `python bot.py`. Enter the two secrets in the service's
**Variables** UI, then deploy. Keep **one replica** and **Serverless disabled**.
This is a long-polling worker: no domain, inbound port or HTTP healthcheck is needed.
Do not run another instance using the same Telegram token. For redeploys, avoid
overlapping the old and new workers; stop the old deployment if Telegram reports Conflict.

Startup verifies Telegram credentials and makes a tiny OpenAI request (billable).
Successful logs contain `Startup verified: Telegram authenticated and OpenAI response OK`.
Then send `/start`, a normal message, and a follow-up in Telegram to verify the
complete message path. AuthenticationError: check API key; RateLimitError: check
API billing/quota; InvalidToken: check Telegram token; Conflict: stop duplicate worker.
Failed startup exits nonzero; use Railway's On Failure restart policy.

## Commands and memory

- `/start`, `/help`: introduction and commands.
- `/reset`: erase this user's server-side memory.
- `/privacy`: explain message processing.

Only private text chats are processed. Each Telegram user has a separate bounded
history of 10 exchanges, expiring after 24 hours of inactivity. Memory is RAM-only,
cleared on restart/redeploy, and limited to 1,000 users (oldest sessions evicted).
Updates are processed sequentially to preserve ordering; suitable for a small bot.
Input is capped at 4,000 characters and output at 300 tokens. At higher traffic,
add per-user scheduling, rate limits and a persistent datastore before scaling.

User text and recent history are sent to OpenAI Responses API with `store=False`.
This does not eliminate provider abuse-monitoring retention. No message text,
keys or raw exception payloads are logged. `/reset` does not erase Telegram history
or provider records. Keep API spending limits appropriate for your audience.

## Tests

`python -m unittest discover -s tests -v`

References: [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create),
[python-telegram-bot](https://docs.python-telegram-bot.org/en/stable/).
