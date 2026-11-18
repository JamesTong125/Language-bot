# Language Immersion Buddy

A web app for practising a target language through role-played real-life scenarios. The learner
chats with an AI partner, gets gentle corrections after each message, and builds a vocabulary
deck from their own mistakes.

The app is built in phases (see the build spec). **Current status: Phase 2, Text conversation.**
Accounts, onboarding, profiles, data export, and account deletion work (Phase 1). Learners can
pick a scenario and hold a streamed text conversation with the AI partner, with optional hints
(Phase 2). Corrections arrive in Phase 3.

| Part     | Stack                                                    | Folder      |
| -------- | -------------------------------------------------------- | ----------- |
| web      | Next.js 16 (App Router), TypeScript strict, Tailwind 4   | `frontend/` |
| api      | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2 (async)  | `backend/`  |
| db       | PostgreSQL 16, migrations with Alembic                   | `db/`       |

Design decisions are logged in [docs/decisions.md](docs/decisions.md).

## Quick start

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine
with the Compose plugin), plus free API keys from
[Google AI Studio](https://aistudio.google.com/apikey) and [Groq](https://console.groq.com/keys).

```sh
cp .env.example .env      # then fill in JWT_SECRET, LLM_CHAT_API_KEY, LLM_ANALYSIS_API_KEY
docker compose up
```

Then open <http://localhost:3000>. The first start takes a few minutes while images build.

- Web app: <http://localhost:3000>
- API: <http://localhost:8000> (interactive docs at <http://localhost:8000/docs>)
- PostgreSQL: `localhost:5432`, user `immersion`, password `immersion`, database `immersion`

The API applies database migrations on every start (`alembic upgrade head`). Code changes in
`backend/` and `frontend/` reload automatically. After adding a new route folder in
`frontend/app/`, run `docker compose restart web`.

To check your LLM keys and models, run `docker compose exec api python -m scripts.llm_smoke`.
It sends one short request to each configured provider and prints the timing. Add model IDs
to try other models with the chat provider's key, for example
`... llm_smoke gemini-3.8-flash gemini-3.5-flash-lite`.

To stop, press Ctrl+C or run `docker compose down`. To also delete the database volume, run
`docker compose down -v`.

## Environment variables

Compose reads `.env` from the repo root. `.env.example` lists every variable.

| Variable              | Used by | Default                                    | Purpose                                                 |
| --------------------- | ------- | ------------------------------------------ | ------------------------------------------------------- |
| `DATABASE_URL`        | api     | set by Compose to the `db` service         | SQLAlchemy URL. Must use the `postgresql+asyncpg://` driver. |
| `JWT_SECRET`          | api     | a dev-only value in `docker-compose.yml`   | Signs login tokens. At least 32 characters. **Set a random value outside local dev.** |
| `CORS_ORIGIN`         | api     | `http://localhost:3000`                    | The one origin allowed to call the API with cookies.    |
| `COOKIE_SECURE`       | api     | `false`                                    | Set `true` when serving over https.                     |
| `NEXT_PUBLIC_API_URL` | web     | `http://localhost:8000`                    | Where the browser sends API requests.                   |
| `LLM_CHAT_BASE_URL`, `LLM_CHAT_API_KEY`, `LLM_CHAT_MODEL` | api | Gemini OpenAI-compatible endpoint, `gemini-3.8-flash` | The conversation partner. |
| `LLM_ANALYSIS_BASE_URL`, `LLM_ANALYSIS_API_KEY`, `LLM_ANALYSIS_MODEL` | api | `https://api.groq.com/openai/v1`, `openai/gpt-oss-20b` | Hints now; error analysis and wrap-up later. |
| `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL` | api | not set | Used when the main provider is rate limited, down, or times out. For example Ollama at `http://host.docker.internal:11434/v1`. |
| `LLM_DAILY_REQUEST_BUDGET` | api | not set | Soft cap. Logs a warning at 80% and 100% of daily requests. |
| `LLM_<ROLE>_REASONING_EFFORT` | api | not set | `low`, `medium`, etc. for thinking models. `low` makes Gemini and gpt-oss much faster. |
| `LLM_<ROLE>_MAX_TOKENS` | api | `1024` | Output token cap per call. Reasoning tokens count against it. |
| `LLM_<ROLE>_JSON_MODE` | api | `false` | Use the provider's native JSON mode. Only for providers that support it. |
| `LLM_TIMEOUT_SECONDS` | api | `30` | Per request, and per gap between streamed chunks. |
| `LLM_MAX_RETRIES` | api | `2` | Retries on 429 and 5xx before switching to the fallback. |
| `LLM_HISTORY_TURNS` | api | `20` | Turns of conversation history sent with each reply. |

`<ROLE>` is `CHAT`, `ANALYSIS`, or `FALLBACK`. Generate a JWT secret with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

API keys stay on the server. The browser only talks to the FastAPI backend.

## LLM providers and your data

Conversations are personal data. Check each provider's terms before you use it. Summaries
below were checked in November 2026.

| Provider | Data policy |
| -------- | ----------- |
| Google Gemini, free tier | Google uses prompts and responses from unpaid quota to improve its products, and human reviewers may read them. The terms say not to send sensitive, confidential, or personal information. Paid quota (a Cloud project with billing) is not used this way, and in the EEA, Switzerland, and the UK the paid-tier terms apply to free use too. [Terms](https://aistudio.google.com/docs/terms#unpaid-services) |
| Groq | Inference inputs and outputs are not retained by default. They may be logged for up to 30 days for reliability or abuse checks, unless you turn on Zero Data Retention in Groq's Data Controls. [Your data](https://console.groq.com/docs/your-data) |
| Ollama (local) | Runs on your machine. Nothing leaves it. |

For fully private practice, point `LLM_CHAT_*` and `LLM_ANALYSIS_*` at a local Ollama server.
A per-session "private" switch is planned for a later phase.

## Running checks

Backend tests run against a separate `immersion_test` database in the Compose `db` service.
The LLM is always mocked with `FakeLLMClient`; tests never call a real provider.
With the stack running:

```sh
docker compose exec api pytest          # tests
docker compose exec api ruff check .    # lint
docker compose exec api mypy app tests  # types
docker compose exec api alembic check   # models and migrations agree
```

Frontend:

```sh
cd frontend
npm install
npm run lint
npx tsc --noEmit
npm run build
```

If you created the database volume before `db/init/01-test-db.sql` existed, create the test
database once with
`docker compose exec db createdb -U immersion immersion_test`.

## API

| Method and path              | Purpose                                                        |
| ---------------------------- | -------------------------------------------------------------- |
| `POST /auth/register`        | Create an account and set the session cookie                   |
| `POST /auth/login`           | Log in and set the session cookie                              |
| `POST /auth/logout`          | Clear the session cookie                                       |
| `GET /profile`               | Email, native language, current profile, all profiles          |
| `PUT /profile`               | Set native language, target language, level, goals             |
| `GET /scenarios`             | Built-in scenarios plus the learner's custom ones              |
| `POST /sessions`             | Start a session (`{"scenario_id"}`); returns the opening line  |
| `GET /sessions/{id}`         | Full transcript                                                |
| `POST /sessions/{id}/turns`  | `{"text"}` or `{"retry": true}`; streams the reply over SSE    |
| `POST /sessions/{id}/hint`   | Suggestions for what to say next                               |
| `GET /account/export`        | Download all of the user's data as JSON                        |
| `DELETE /account`            | Delete the user and all related data (body: `{"password"}`)    |
| `GET /debug/llm-usage`       | Requests and tokens per provider per day, and budget used      |
| `GET /languages`             | Supported languages and CEFR levels                            |
| `GET /health`                | Liveness check, including the database                         |

The session is a JWT in an httpOnly, `SameSite=Lax` cookie named `access_token`.

The turns endpoint streams these SSE events: `learner_turn` (the saved message), `token`
(`{"text"}` chunks), then `done` (the saved partner turn) or `error` (`{"message", "retryable"}`).
The learner message is always kept, so after an `error` the client can send `{"retry": true}`.

## Project layout

```
backend/
  app/
    main.py          app factory, CORS, routers
    config.py        settings from env vars
    db.py            async engine and session dependency
    deps.py          current user, current profile, and LLM client dependencies
    languages.py     supported languages and CEFR levels
    llm/             provider layer: LLMClient protocol, OpenAI-compatible client,
                     retries and fallback, JSON validation, usage tracking
    prompts/         versioned prompt files (*_v1.md)
    conversation/    prompt builders (pure functions)
    models/          SQLAlchemy models
    schemas/         Pydantic request and response models
    routers/         HTTP endpoints, kept thin
    services/        database logic and conversation flow
    security/        password hashing, JWT, cookies
  alembic/           migrations (one revision per phase)
  scripts/           manual tools, e.g. llm_smoke.py
  tests/             pytest suite; tests/fakes.py holds FakeLLMClient
frontend/
  app/               pages: landing, login, register, onboarding, home, profile, sessions/[id]
  components/        AppShell, forms, ScenarioPicker, conversation/ (chat UI, hints)
  lib/               API client, SSE reader, types
db/init/             SQL run when the Postgres volume is first created
docs/decisions.md    decision log
```
