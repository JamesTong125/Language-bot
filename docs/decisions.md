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
