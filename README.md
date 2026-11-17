# Language Immersion Buddy

A web app for practising a target language through role-played real-life scenarios. The learner
chats with an AI partner, gets gentle corrections after each message, and builds a vocabulary
deck from their own mistakes.

The app is built in phases (see the build spec). **Current status: Phase 1, Foundation.**
Accounts, login, onboarding, profiles, data export, and account deletion work. Scenarios and
conversations arrive in Phase 2.

| Part     | Stack                                                    | Folder      |
| -------- | -------------------------------------------------------- | ----------- |
| web      | Next.js 16 (App Router), TypeScript strict, Tailwind 4   | `frontend/` |
| api      | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2 (async)  | `backend/`  |
| db       | PostgreSQL 16, migrations with Alembic                   | `db/`       |

Design decisions are logged in [docs/decisions.md](docs/decisions.md).

## Quick start

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine
with the Compose plugin).

```sh
cp .env.example .env      # optional for now; every Phase 1 setting has a dev default
docker compose up
```

Then open <http://localhost:3000>. The first start takes a few minutes while images build.

- Web app: <http://localhost:3000>
- API: <http://localhost:8000> (interactive docs at <http://localhost:8000/docs>)
- PostgreSQL: `localhost:5432`, user `immersion`, password `immersion`, database `immersion`

The API applies database migrations on every start (`alembic upgrade head`). Code changes in
`backend/` and `frontend/` reload automatically.

To stop, press Ctrl+C or run `docker compose down`. To also delete the database volume, run
`docker compose down -v`.

## Environment variables

Compose reads `.env` from the repo root. Copy `.env.example` to start.

| Variable              | Used by | Default                                    | Purpose                                                 |
| --------------------- | ------- | ------------------------------------------ | ------------------------------------------------------- |
| `DATABASE_URL`        | api     | set by Compose to the `db` service         | SQLAlchemy URL. Must use the `postgresql+asyncpg://` driver. |
| `JWT_SECRET`          | api     | a dev-only value in `docker-compose.yml`   | Signs login tokens. At least 32 characters. **Set a random value outside local dev.** |
| `CORS_ORIGIN`         | api     | `http://localhost:3000`                    | The one origin allowed to call the API with cookies.    |
| `COOKIE_SECURE`       | api     | `false`                                    | Set `true` when serving over https.                     |
| `NEXT_PUBLIC_API_URL` | web     | `http://localhost:8000`                    | Where the browser sends API requests.                   |

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

The LLM variables from the spec (`LLM_CHAT_*`, `LLM_ANALYSIS_*`, `LLM_FALLBACK_*`,
`LLM_DAILY_REQUEST_BUDGET`) are added in Phase 2, together with each provider's data policy.

## Running checks

Backend tests run against a separate `immersion_test` database in the Compose `db` service.
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

## API (Phase 1)

| Method and path        | Purpose                                                        |
| ---------------------- | -------------------------------------------------------------- |
| `POST /auth/register`  | Create an account and set the session cookie                   |
| `POST /auth/login`     | Log in and set the session cookie                              |
| `POST /auth/logout`    | Clear the session cookie                                       |
| `GET /profile`         | Email, native language, current profile, all profiles          |
| `PUT /profile`         | Set native language, target language, level, goals             |
| `GET /account/export`  | Download all of the user's data as JSON                        |
| `DELETE /account`      | Delete the user and all related data (body: `{"password"}`)    |
| `GET /languages`       | Supported languages and CEFR levels                            |
| `GET /health`          | Liveness check, including the database                         |

The session is a JWT in an httpOnly, `SameSite=Lax` cookie named `access_token`.

## Project layout

```
backend/
  app/
    main.py          app factory, CORS, routers
    config.py        settings from env vars
    db.py            async engine and session dependency
    deps.py          current-user dependency
    languages.py     supported languages and CEFR levels
    models/          SQLAlchemy models
    schemas/         Pydantic request and response models
    routers/         HTTP endpoints, kept thin
    services/        database logic
    security/        password hashing, JWT, cookies
  alembic/           migrations (one revision per phase)
  tests/
frontend/
  app/               pages: landing, login, register, onboarding, home, profile
  components/        AppShell (auth guard and nav), forms, UI primitives
  lib/               API client and types
db/init/             SQL run when the Postgres volume is first created
docs/decisions.md    decision log
```
