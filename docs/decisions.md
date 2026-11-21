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

## Phase 3: Corrections

### D22. Analysis runs as an asyncio task, not FastAPI BackgroundTasks
The spec suggests BackgroundTasks, but with a streaming response those only start after the
stream closes, which would delay corrections until after the reply. `services/analysis.py`
starts an `asyncio` task as soon as the learner turn is saved, so the analysis call and the
partner reply run in parallel. The task saves corrections with its own DB session and never
raises. A module-level set keeps references so tasks aren't garbage collected.

### D23. Corrections arrive on the same SSE stream
After `done` (or `error`), the stream waits up to 45 seconds for the analysis and sends
`corrections` with `{"turn_id", "status": "ok" | "failed", "corrections": [...]}`, then
closes. The wait is shielded: if it times out or the client leaves, the analysis still
finishes and saves, and the corrections show on the next transcript load. A retry
(`{"retry": true}`) doesn't re-run analysis; the message was analysed when it was sent.

### D24. No "analysed" flag on turns
A learner turn with no corrections looks the same whether it was correct or the analysis
failed. The spec says to store nothing on failure, so this needs no schema change. The live
UI shows "Checking your message…" until the `corrections` event or the end of the stream.

### D25. Two layers of output checks
`AnalysisOut` (Pydantic) checks shape: error type from the fixed set (spellings like
"Word order" are normalised to `word_order`), severity 1 to 3, non-empty spans, at most 8
items. A shape failure triggers the single retry. Then `usable_corrections` drops items that
are well formed but unusable: a span that isn't in the learner's message (ignoring case,
spacing, and curly apostrophes), a "fix" that only changes case, and duplicates. Dropping
single items avoids a retry that would cost quota for one bad item.

### D26. What the analysis model sees
Rules first in a static system prompt (target, native language, level), one short example,
and the learner's message in a separate user message with the previous partner line and
the scene (title and persona) for context. The scene lets the model judge register: slang
is flagged in a job interview but fine at a café. The prompt also tells the model not to
assume the learner's gender, after it "corrected" a correct `organisé` to `organisée`.

### D27. Suggested vocab items wait for Phase 4
The spec lets analysis return optional vocab suggestions. Nothing could store them before
the `vocab_items` table exists, so Phase 4 adds them to the analysis schema as
`analysis_v2`, keeping this prompt small for the small model.

### D28. Seeded correction cases
`backend/tests/data/correction_cases.json` holds learner messages with known mistakes
(Spanish, French, and German with Spanish explanations) and correct messages that must get
no corrections. The test suite checks the pipeline with a fake model.
`python -m scripts.eval_corrections --runs N` runs them against the real analysis model.
A case passes when every expected mistake is found; extra valid fixes are allowed.
Result on `openai/gpt-oss-20b`, reasoning effort low: 20/20 (10 cases, 2 runs each).

### D29. Chip display
"register" shows as "Tone" to learners. Chip colour follows severity (blue, amber, rose)
and the severity is also given in text for screen readers. Chips are buttons with
`aria-expanded`, so they work with the keyboard.

## Phase 4: Vocabulary and review

### D30. Scheduler details (`backend/app/srs/scheduler.py`)
`schedule(item, rating, now) -> item` is pure and returns a new `SrsState`.
- Every rating updates the ease with the SM-2 formula `ease + 0.1 - (5-q)(0.08 + (5-q)0.02)`,
  never below 1.3. So a 5 adds 0.1, a 4 keeps it, and a 3 or lower lowers it.
- Ratings 0 to 2: repetitions reset to 0, interval 1 day.
- Ratings 3 to 5: repetitions + 1; intervals 1 day, then 6 days, then
  `round(previous interval * new ease)`. With steady 4s: 1, 6, 15, 38, 95 days.
- `due_at = now + interval`. New cards have ease 2.5, interval 0, and are due right away.
`backend/tests/test_scheduler.py` is the specification; the API test replays ratings through
`POST /vocab/{id}/review` and checks each result against `schedule`.

### D31. Two columns added to `vocab_items` (data model change)
- `session_id` (nullable, `ON DELETE SET NULL`): the session whose wrap-up created the card.
  The summary page lists "the new vocab items" of a session, which the spec's fields can't
  express: words the partner used have no `source_correction_id`.
- `created_at`, for sorting the deck newest first.
Also a unique index on `(learner_profile_id, lower(term))` as a safety net under the
application-level deduplication (D34). **Please confirm or say if you'd prefer otherwise.**

### D32. Wrap-up output and storage
One call to the analysis model (`wrapup_v1`) returns a flat JSON object:
`went_well`, `recurring_mistakes` (up to 3), `practice` (exactly 3), and `vocab` (up to 10
items with `term`, `translation`, `example_sentence`, `source`). It's flat because the small
model broke nested objects in testing; Groq's native JSON mode is now on for analysis
(`LLM_ANALYSIS_JSON_MODE=true` in `.env`) for the same reason. Corrections are numbered C1,
C2, ... in the prompt, and `source: "C2"` links a card to its correction; unknown ids are
ignored. Validation rejects summaries that list bare ids ("C1, C2") instead of describing
the mistake. `sessions.summary` stores the three summary parts as JSON text.

### D33. Which words become cards
- Every correction becomes a card. If the model leaves one out, a card is made from the
  correction itself: the corrected text, with the explanation as the back of the card.
- At most 3 other words (new words the partner used), and not words the learner typed
  themselves. The small model padded the list with "por favor" and "sí" without this.
- This replaces D27's plan to add vocab suggestions to the per-message analysis: the wrap-up
  sees the whole session, and the analysis prompt stays small.

### D34. Deduplication
Terms are compared after lowercasing, collapsing spaces, trimming edge punctuation, and
dropping one leading article for the target language (es, fr, it, pt, de, nl, sv, en), so
"un café", "el café" and "café." are one card. Accents count: "papa" and "papá" differ.
Deduplication is per learner profile, so the same word can be in the Spanish and French
decks. The insert uses `ON CONFLICT DO NOTHING` on the unique index for races.

### D35. Ending a session
`POST /sessions/{id}/end` waits up to 20 seconds for corrections still in progress, so the
last message's mistakes make it into the wrap-up. It locks the session row before saving,
so two clicks can't save two wrap-ups, and ending again returns the saved result. If the
LLM fails, nothing is saved and the session stays open (503). A session with no learner
messages ends without an LLM call. `error_rate` is the share of learner messages with at
least one correction, from 0 to 1.

### D36. Endpoints added beyond the spec's table
- `DELETE /vocab/{id}`: the summary page needs "an option to remove" each new card.
- `GET /sessions/{id}/summary`: reload the summary page without ending again.
`GET /vocab` filters: `all`, `due`, `new` (never reviewed), `learning`, `mistakes`, plus
`q` (search term or translation, wildcards escaped) and `page`/`page_size`. Both
`GET /vocab` and `GET /vocab/review` return `due_count` for the home page prompt.

### D37. Review UI
Space or Enter shows the answer; keys 0 to 5 rate it. Labels: Forgot, Wrong, Almost, Hard,
Good, Easy. After each rating the page says when the card comes back. The review page
reloads due cards each time it's shown (Next.js keeps hidden pages mounted). The
"already in your deck" count is passed in the URL right after ending, since it isn't stored.

## Phase 5: Voice

### D38. Browser speech only, with feature detection
Voice uses the Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition` and
`speechSynthesis`), detected at runtime in `frontend/lib/speech.ts`. The language comes from
each language's BCP 47 tag in `GET /languages` (D10), using the session's language. No audio
reaches the server. Chrome and Edge send recognition audio to their vendor's speech service;
Safari may process it on the device. Firefox has no recognition, so it falls back to typing.

### D39. How voice works in a conversation
- Every message has a speaker button that reads it aloud; pressing it again stops.
- The microphone button fills the message box with what was heard, live, and leaves it for
  the learner to check and send. Recognition mistakes are common, and the analysis would
  otherwise "correct" words the learner never said.
- The hands-free switch reads each partner reply aloud, listens, and sends the answer
  automatically. It never listens while speaking, so the partner's voice isn't picked up.
  After three silent attempts it pauses with a note; pressing the microphone resumes.
- Errors that will repeat (microphone blocked, no microphone, no network, unsupported
  language) show a message and switch hands-free off. Typing always works.
- Voice stops when the learner leaves the page, since Next.js keeps hidden pages mounted.

### D40. How voice is tested
Real recognition can't run in headless browser tests. The browser test replaces the speech
APIs with scripted fakes: a full hands-free session (three spoken answers, every reply read
aloud in es-ES), the manual microphone, a blocked microphone, and a browser with no speech
APIs at all, which hides the voice controls and keeps typing. Trying it with a real
microphone in Chrome or Edge is still worth doing by hand.

## Phase 6: Adaptation and polish

### D41. Two columns added to `sessions` (data model change)
- `cefr_level`: the learner's level when the session started. Level suggestions compare only
  sessions at the current level, so after a level change the old sessions stop counting.
  The partner also keeps that level for the whole session. Migration `0005` fills it in for
  existing sessions with the profile's current level.
- `is_private` (D44).
**Please confirm or say if you'd prefer otherwise.**

### D42. Level suggestions (`backend/app/progress/level.py`)
The last 3 ended sessions at the current level with at least 3 learner messages each. An
average error rate of 20% or less suggests moving up one level; 60% or more suggests moving
down. Nothing changes until the learner presses "Switch to ...", which saves the profile.
"Stay at ..." hides that suggestion in this browser (local storage) until newer sessions give
a new one. The suggestion shows on the home page and the Progress page.

### D43. Custom scenarios
`POST /scenarios` with `{"description"}` (8 to 300 characters) asks the analysis model
(`scenario_v1`) for a title, description, partner persona, and goal, written in the learner's
native language. The scenario is saved for the current target language at the learner's
current level, and only its creator sees it. The description goes in a separate message as
data. The model can refuse unsuitable topics (`{"refused": true}`), which returns 422 and
saves nothing. There's no delete yet: deleting a scenario would also delete its sessions.

### D44. Private sessions
The spec asks to "let the learner pick the local provider for private sessions". A new
optional provider config, `LLM_PRIVATE_*`, is meant for a local Ollama server. When it's
set, the scenario picker shows a "Private session" option. Every call in a private session
(opening, replies, analysis, hints, wrap-up) goes to that provider only, with no fallback,
so nothing reaches a cloud provider. If the private provider is later removed, the session's
requests fail with 503 instead of silently using the cloud.

### D45. Rate limits
Counted from rows already in the database, so they hold across restarts: learner messages per
user per minute (default 10), sessions started per rolling 24 hours (30), and custom scenarios
per 24 hours (10). Over the limit returns 429 with a `Retry-After` header and saves nothing.
Set a limit to 0 to turn it off. They're soft limits: two requests at the same instant can
both pass. Retries of a failed reply aren't counted, since they don't add a message.

### D46. Dashboard (`GET /stats`)
- Streak: consecutive days with a message sent or a card reviewed, in any language. It
  counts until today ends, so practising yesterday but not yet today keeps it.
- Sessions per week (8 weeks, Monday start), mistakes per session (last 10 ended sessions,
  oldest first), the most common mistake types, totals, and level progress.
- Days and weeks use the browser's time zone (`tz`, an IANA name) and are computed in
  Postgres. Unknown zones fall back to UTC.
- Everything except the streak is for the current language.
