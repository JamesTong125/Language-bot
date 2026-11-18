# Decisions

Choices made while building that the spec left open. Each entry says what was decided and why.
Scope changes approved by the project owner are marked **(approved)**.

## Scope additions

### D1. Data export endpoint: `GET /account/export` (approved)
The privacy requirements ask for data export, but the API table had no endpoint for it.
`GET /account/export` returns everything stored about the signed-in user as one JSON document
(sent with `Content-Disposition: attachment`). Each phase that adds a table extends the export,
so the export always covers all of the user's data. Password hashes are never exported.

### D2. Hint endpoint: `POST /sessions/{id}/hint` (approved, built in Phase 2)
The conversation page has a "suggest what to say next" toggle, but no endpoint or LLM call was
listed for it. `POST /sessions/{id}/hint` uses the analysis model config (the cheaper, faster one)
with its own versioned prompt file, `backend/app/prompts/hint_v1.md`. It returns one or two short
suggestions in the target language at the learner's level. Hints are not stored as turns.

## Phase 1: Foundation

### D3. Learners can have one profile per target language
`learner_profiles` has `UNIQUE (user_id, target_language)`. Sessions and vocab items hang off a
profile, so switching target language keeps each language's deck and history separate.
The "current" profile is the most recently updated one, so the table gets an `updated_at`
column (the only addition to the spec's key fields). `PUT /profile` upserts the profile for the
given target language and makes it current.

### D4. `users.native_language` is nullable
Registration only needs email and password. Onboarding sets the native language right after,
through `PUT /profile`. Endpoints that need a native language treat "not set" as "not onboarded".

### D5. Async SQLAlchemy with asyncpg
Streaming replies (SSE) and background analysis are I/O bound, so the API uses
SQLAlchemy 2 async sessions with the asyncpg driver. Alembic runs migrations through the same
async engine.

### D6. One migration per phase
Each phase adds the tables it needs in its own Alembic revision, instead of creating the full
schema up front. Phase 1 creates `users` and `learner_profiles`.

### D7. Auth details
- Passwords: argon2id via `argon2-cffi`.
- Tokens: HS256 JWT (PyJWT), 7-day expiry, in an httpOnly cookie named `access_token` with
  `SameSite=Lax`. `Secure` is controlled by `COOKIE_SECURE` (off for local http, on in production).
- Login checks a dummy hash when the email is unknown, so response time does not reveal which
  emails are registered. Errors say "Invalid email or password" in both cases.
- CSRF: the cookie is `SameSite=Lax`, CORS allows only `CORS_ORIGIN`, and state-changing
  endpoints take JSON bodies, which forces a CORS preflight from other origins.

### D8. Account deletion asks for the password
`DELETE /account` takes `{"password": "..."}` in the body, so a stolen session cookie alone
cannot wipe an account. All related rows go with it through `ON DELETE CASCADE`.

### D9. Browser talks to the API directly
The browser calls the FastAPI service at `NEXT_PUBLIC_API_URL` with `credentials: "include"`,
and the API allows `CORS_ORIGIN`. `localhost:3000` and `localhost:8000` are the same site, so the
`SameSite=Lax` cookie is sent. A Next.js rewrite proxy was rejected because proxies can buffer
SSE, which would break streamed partner replies in Phase 2.

### D10. Supported languages are a fixed list
`backend/app/languages.py` lists the supported languages as ISO 639-1 codes (with a BCP 47 tag
for the Web Speech API in Phase 5). The API rejects unknown codes and a target language equal to
the native language. The frontend reads the list from `GET /languages` so there is one source.

### D11. Tests run against real PostgreSQL
Backend tests use a separate `immersion_test` database on the Compose `db` service, created by
`db/init/01-test-db.sql`. Tables are created fresh per test run and truncated between tests.
This catches Postgres-specific behaviour (constraints, cascades) that SQLite would hide.

### D12. Dev servers poll for file changes inside Docker
Bind mounts from Windows and macOS hosts don't deliver file-change events into containers, so
hot reload silently stopped working. Compose sets `WATCHFILES_FORCE_POLLING=true` for uvicorn and
`NEXT_WATCH_POLL_MS=1000`, which `next.config.ts` maps to Next's `watchOptions.pollIntervalMs`.
Running `npm run dev` outside Docker doesn't poll.
Note: polling picks up edits to existing files, but a newly added route folder (e.g.
`app/sessions/[id]/`) can need `docker compose restart web`.

## Phase 2: Text conversation

### D13. Built-in scenarios work in any target language
The 9 built-in scenarios (seeded by migration `0002`) have `target_language = NULL`. Their
persona and goal are written in English, and the partner plays them in the learner's target
language. Custom scenarios (Phase 6) will set `target_language`. `GET /scenarios` returns
built-ins plus the learner's own scenarios for their current target language, easiest first.
A scenario's `cefr_level` is its difficulty; the partner always speaks at the learner's level.

### D14. Reply length for B1
The spec gives 1 to 3 short sentences for A1 to A2 and up to 5 for B2 and above. B1 uses
2 to 4 sentences.

### D15. Retry uses the existing turns endpoint
`POST /sessions/{id}/turns` takes `{"text": "..."}` for a new message or `{"retry": true}` to
re-request the partner reply to the last learner message. The learner message is saved before
the LLM call, so a failure never loses it. The UI shows a retry control whenever the last saved
turn is from the learner, including after a page reload. No new endpoint was added.

### D16. SSE event contract
The turns endpoint streams `learner_turn` (the saved message), `token` (`{"text"}` chunks), and
then `done` (the saved partner turn) or `error` (`{"message", "retryable"}`). The partner turn is
saved only when the stream completes; partial text from a failed stream is discarded. The
frontend reads the stream with `fetch` because `EventSource` only supports GET.

### D17. The opening line is generated before the session is saved
`POST /sessions` asks the LLM for the opening line first and saves the session and turn in one
transaction. If every provider fails, it returns 503 and nothing is stored.

### D18. LLM layer structure (`backend/app/llm/`)
- `base.py`: the `LLMClient` protocol (`stream_chat`, `complete_json`) and error types.
- `openai_compat.py`: the single implementation over the openai SDK (`AsyncOpenAI`, SDK
  retries off). Stream timeouts apply to each gap between chunks (`LLM_TIMEOUT_SECONDS`).
- `failover.py`: `FailoverClient` retries 429/5xx with full-jitter exponential backoff
  (`LLM_MAX_RETRIES`), then moves to the fallback provider. Timeouts and rejected requests go
  straight to the fallback. Once text has streamed to the client, a failure is not retried,
  so replies are never spliced from two models.
- `json_output.py`: strips code fences and stray prose, parses, validates with Pydantic, and
  retries once with the validation error. Invalid output twice raises and stores nothing; it
  does not fail over, to avoid spending quota on a model that misbehaves.
- `usage.py`: upserts requests and tokens per provider host, model, and UTC day into
  `llm_usage`, and logs token counts per session tag (never text). `GET /debug/llm-usage`
  (signed in) reports the totals and the share of `LLM_DAILY_REQUEST_BUDGET` used.
- `factory.py`: builds the chat client (chat, then fallback) and the analysis client
  (analysis, then fallback) from env vars. A fallback identical to the primary is skipped.

### D19. Extra env vars for provider differences
Beyond the spec's variables: `LLM_<ROLE>_REASONING_EFFORT` (thinking models are much faster
on `low`), `LLM_<ROLE>_MAX_TOKENS` (output cap per call, default 1024 because reasoning
tokens count against it), `LLM_<ROLE>_JSON_MODE` (native JSON mode flag),
`LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, and `LLM_HISTORY_TURNS`.

### D20. Provider and model choices (checked against provider docs, November 2026)
- Chat default in code is `gemini-3.8-flash`. During setup it and every other full Flash model,
  plus `gemini-4-hydrogen`, returned 503 "high demand" or timed out, while
  `gemini-3.5-flash-lite` answered in about 1 second. The local `.env` uses
  `gemini-3.5-flash-lite` with reasoning effort `low`. Switch back with one line once the
  larger models are available.
- Analysis uses Groq `openai/gpt-oss-20b`. Groq now lists `llama-3.1-8b-instant` as
  Enterprise-only, and gpt-oss-20b is its fastest small model on the standard plan.
- The local `.env` sets the fallback to Groq `openai/gpt-oss-120b` because Ollama isn't
  installed. This means fallback replies are also sent to a cloud provider.
- Groq's Cloudflare front end rejects Python's default `urllib` user agent (error 1010). The
  openai SDK sends its own user agent, so the app is not affected.

### D21. Hints
`POST /sessions/{id}/hint` (see D2) returns 1 to 3 suggestions validated by `HintOut`. The
transcript goes in a separate user message so its lines can't be read as instructions. The UI
fetches a hint once per partner message while the toggle is on, and clicking a suggestion
copies it into the message box.
