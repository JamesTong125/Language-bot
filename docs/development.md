# Development guide

Technical details for working on Language learning bot. For what the app does and how to
start it, see the [README](../README.md). Design decisions are logged in
[decisions.md](decisions.md).

## Services

`docker compose up` starts three services:

- Web app: <http://localhost:3000>
- API: <http://localhost:8000> (interactive docs at <http://localhost:8000/docs>)
- PostgreSQL: `localhost:5432`, user `immersion`, password `immersion`, database `immersion`

The API applies database migrations on every start (`alembic upgrade head`). Code changes in
`backend/` and `frontend/` reload automatically. After adding a new route folder in
`frontend/app/`, run `docker compose restart web`.

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
| `LLM_ANALYSIS_BASE_URL`, `LLM_ANALYSIS_API_KEY`, `LLM_ANALYSIS_MODEL` | api | `https://api.groq.com/openai/v1`, `openai/gpt-oss-20b` | Error analysis, session wrap-up, and hints. |
| `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL` | api | not set | Used when the main provider is rate limited, down, or times out. For example Ollama at `http://host.docker.internal:11434/v1`. |
| `LLM_PRIVATE_BASE_URL`, `LLM_PRIVATE_API_KEY`, `LLM_PRIVATE_MODEL` | api | not set | The model for private sessions, for example a local Ollama server. When set, learners can start private sessions, which use only this provider. |
| `LLM_DAILY_REQUEST_BUDGET` | api | not set | Soft cap. Logs a warning at 80% and 100% of daily requests. |
| `RATE_LIMIT_TURNS_PER_MINUTE` | api | `10` | Learner messages per user per minute. `0` turns it off. |
| `RATE_LIMIT_SESSIONS_PER_DAY` | api | `30` | Sessions started per user per rolling 24 hours. |
| `RATE_LIMIT_SCENARIOS_PER_DAY` | api | `10` | Custom scenarios created per user per rolling 24 hours. |
| `LLM_<ROLE>_REASONING_EFFORT` | api | not set | `low`, `medium`, etc. for thinking models. `low` makes Gemini and gpt-oss much faster. |
| `LLM_<ROLE>_MAX_TOKENS` | api | `1024` | Output token cap per call. Reasoning tokens count against it. |
| `LLM_<ROLE>_JSON_MODE` | api | `false` | Use the provider's native JSON mode. Only for providers that support it. Recommended `true` for Groq. |
| `LLM_TIMEOUT_SECONDS` | api | `30` | Per request, and per gap between streamed chunks. |
| `LLM_MAX_RETRIES` | api | `2` | Retries on 429 and 5xx before switching to the fallback. |
| `LLM_HISTORY_TURNS` | api | `20` | Turns of conversation history sent with each reply. |

`<ROLE>` is `CHAT`, `ANALYSIS`, `FALLBACK`, or `PRIVATE`. Generate a JWT secret with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

API keys stay on the server. The browser only talks to the FastAPI backend.

## Checking the LLM setup

- `docker compose exec api python -m scripts.llm_smoke` sends one short request to each
  configured provider and prints the timing. Add model IDs to try other models with the chat
  provider's key, for example `... llm_smoke gemini-3.8-flash gemini-3.5-flash-lite`.
- `docker compose exec api python -m scripts.eval_corrections --runs 2` runs the seeded
  messages in `backend/tests/data/correction_cases.json` through the real analysis model and
  prints a pass rate.
- `GET /debug/llm-usage` (signed in) shows requests and tokens per provider per day.

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
database once with `docker compose exec db createdb -U immersion immersion_test`.

## API

| Method and path              | Purpose                                                        |
| ---------------------------- | -------------------------------------------------------------- |
| `POST /auth/register`        | Create an account and set the session cookie                   |
| `POST /auth/login`           | Log in and set the session cookie                              |
| `POST /auth/logout`          | Clear the session cookie                                       |
| `GET /profile`               | Email, native language, current profile, all profiles          |
| `PUT /profile`               | Set native language, target language, level, goals             |
| `GET /scenarios`             | Built-in plus the learner's custom scenarios; `private_available` |
| `POST /scenarios`            | Create a custom scenario from `{"description"}`                |
| `POST /sessions`             | Start a session (`{"scenario_id", "private"}`); returns the opening line |
| `GET /sessions/{id}`         | Full transcript with corrections                               |
| `POST /sessions/{id}/turns`  | `{"text"}` or `{"retry": true}`; streams the reply over SSE    |
| `POST /sessions/{id}/hint`   | Suggestions for what to say next                               |
| `POST /sessions/{id}/end`    | Wrap-up: summary, error rate, new cards (duplicates skipped)   |
| `GET /sessions/{id}/summary` | The saved wrap-up of an ended session                          |
| `GET /vocab`                 | Deck: `filter` (all, due, new, learning, mistakes), `q`, pages |
| `GET /vocab/review`          | Cards due now, oldest first                                    |
| `POST /vocab/{id}/review`    | `{"rating": 0-5}`; returns the updated schedule                |
| `DELETE /vocab/{id}`         | Remove a card                                                  |
| `GET /stats?tz=`             | Streak, sessions per week, mistake trend and types, level progress |
| `GET /account/export`        | Download all of the user's data as JSON                        |
| `DELETE /account`            | Delete the user and all related data (body: `{"password"}`)    |
| `GET /debug/llm-usage`       | Requests and tokens per provider per day, and budget used      |
| `GET /languages`             | Supported languages and CEFR levels                            |
| `GET /health`                | Liveness check, including the database                         |

Rate-limited requests return 429 with a `Retry-After` header.

The session is a JWT in an httpOnly, `SameSite=Lax` cookie named `access_token`.

The turns endpoint streams these SSE events: `learner_turn` (the saved message), `token`
(`{"text"}` chunks), then `done` (the saved partner turn) or `error` (`{"message", "retryable"}`).
For a new message, `corrections` (`{"turn_id", "status", "corrections"}`) follows once the
background error analysis finishes, and then the stream closes. The learner message is always
kept, so after an `error` the client can send `{"retry": true}`.

## Voice

Voice runs entirely in the browser through the Web Speech API (`frontend/lib/speech.ts`).
Automated browser tests replace it with scripted fakes, so try a real microphone by hand in
Chrome or Edge: start a session, switch on hands-free, and answer a few lines out loud.
Recognition needs a secure context; `localhost` counts as one.

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
    srs/             spaced-repetition scheduler (pure function)
    progress/        level suggestions and streak/week maths (pure functions)
    models/          SQLAlchemy models
    schemas/         Pydantic request and response models
    routers/         HTTP endpoints, kept thin
    services/        database logic and conversation flow
    security/        password hashing, JWT, cookies
  alembic/           migrations (one revision per phase)
  scripts/           manual tools: llm_smoke.py, eval_corrections.py
  tests/             pytest suite; fakes.py holds FakeLLMClient, data/ the seeded cases
frontend/
  app/               pages: landing, login, register, onboarding, home, profile,
                     sessions/[id], sessions/[id]/summary, vocab, review, progress
  components/        AppShell, forms, ScenarioPicker, conversation/ (chat, chips, hints,
                     summary, voice), vocab/ (deck, review flow), progress/ (dashboard)
  lib/               API client, SSE reader, speech (Web Speech API), types
db/init/             SQL run when the Postgres volume is first created
docs/decisions.md    decision log
```
