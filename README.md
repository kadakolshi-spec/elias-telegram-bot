# Elias — Telegram user account / MTProto

Elias replies to new private text messages using Telethon and OpenAI. Her existing
fictional AI persona and per-user context are preserved. No Bot API token is used.

## Safe local session generation (Windows)

1. Run `Generate-Session.cmd` on your own computer (Python with Tkinter required).
2. Enter API ID, API hash, the Elias account phone number, Telegram login code and,
   if requested, 2FA password in the local terminal. Input is hidden.
3. A local window provides **Copy** buttons for the three Telegram variables.
   Paste each directly into Railway > this service > Variables > New Variable.
   Keep the local window open until saved, then use **Done** to clear its clipboard.
4. Keep the existing `OPENAI_API_KEY` in Railway, or enter it there directly.

No credentials are printed, written to files, or sent to chat. The script connects
only to Telegram for login. Clipboard content is sensitive: avoid clipboard history
or cloud clipboard sync while transferring it. Anyone holding a session can access
the account; revoke the `Elias Session Setup` session in Telegram Settings > Devices
if compromised. The process never asks a deployed service to sign in interactively.

## Railway configuration

Required: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`, `OPENAI_API_KEY`.
Optional: `OPENAI_MODEL` (default `gpt-4.1-mini`). `.env.example` is a template only;
production reads environment variables and does not load local `.env` files.
`TELEGRAM_BOT_TOKEN` is obsolete and can be removed after successful migration.

Use the Dockerfile and `railway.toml`, one replica, no public HTTP domain or HTTP
healthcheck. Stop the old deployment before starting the user-session worker to
avoid overlap. Session must belong to a normal user account, not a bot. The worker
checks Telegram authorization and an OpenAI response before logging readiness.

## Behavior and limits

- Replies only to new incoming private text messages after startup; no history scan,
  contact imports, broadcasts, scheduled messages or group/channel responses.
- Ignores self, Telegram service account, bots, edited messages and duplicate events.
- At most 5 accepted messages per user per minute, at least 3 seconds apart;
  at most 20 accepted messages globally per minute and 4 simultaneous handlers.
- Extra messages are silently skipped, including messages received while that user
  has a reply in progress. No unbounded backlog or rate-limit warning spam.
- Telegram FloodWait pauses outgoing replies globally. No immediate retry or error
  reply loop. Limits and duplicate tracking reset at restart; use one replica.
- Context: original bounded in-memory policy, 10 exchanges/user, 24-hour expiry,
  maximum 1,000 users. Restart clears it. Existing Bot API in-memory conversations
  cannot survive migration; no persistent history existed in the original version.
- `/start`, `/help`, `/privacy`, `/reset` work in private chats. OpenAI receives text
  and context with `store=False`. Logs contain no text, credentials, or user IDs.

## Validation

`python -m unittest discover -s tests -v`

Live acceptance after secrets are saved and deployment reports readiness:
1. Send Elias a private text from a different human Telegram account.
2. Confirm a reply and Railway log `Private message reply sent`.
3. Wait at least 3 seconds, ask a follow-up referencing the first message, check context.
4. Send `/reset`; check a new conversation. Groups/outgoing messages must not trigger replies.

A successful build alone is not a successful live acceptance test.

References: https://docs.telethon.dev/en/stable/basic/signing-in.html and
https://docs.telethon.dev/en/stable/concepts/sessions.html
