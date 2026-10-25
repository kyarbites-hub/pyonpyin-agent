# PyonPyin Architecture

## Current MVP storage/worker update — 2026-10-25

The local MVP defaults to SQLite when no Sheets spreadsheet is configured;
`.env.example` explicitly selects SQLite. `storage.py` selects the backend,
`sqlite_store.py` supplies transactional persistence and durable job claims,
`worker.py` runs generation/discovery/Azure audio outside HTTP requests, and
`mvp_api.py` exposes UI-independent original review, publication and audio workflows.
Database and audio share a persistent host/volume (`compose.yaml`). GitHub dispatch
is disabled for local SQLite. The Sheets-specific architecture below remains an
optional legacy integration. See [current setup](MVP_SETUP_MM.md) and
[API contract](MVP_API.md) for the implemented MVP boundaries and limitations.

## Verified current state

This document describes the checked-in layout and current worktree on
2026-10-13. No live services, deployment, or workflow were contacted during
this inspection. Existing uncommitted work was preserved.

The repository is a **modular monolith with a single React SPA**, plus
independently invoked GitHub Actions jobs. Several domain boundaries already
have separate modules, but neither the public site and admin dashboard nor the
Flask API and pipeline are independently deployed applications today.

## Repository map

```text
.
├── .github/workflows/
│   ├── gemini-test.yml            # offline CI + explicitly requested live smoke test
│   ├── process-stories.yml       # scheduled/dispatch, opt-in one-draft worker
│   └── story-finder.yml           # scheduled/manual discovery worker
├── data/
│   └── approved_sources.json     # explicit source allowlist and discovery policy
├── docs/                         # setup, deployment, testing, architecture, plans
├── frontend/                     # one React + TypeScript + Vite application
│   └── src/
│       ├── App.tsx               # public and admin routes/layouts/components
│       ├── api.ts                # same-origin Flask API client
│       ├── demo.ts               # visibly labelled local demo fixtures
│       └── DemoAudioPlayer.tsx   # synthetic UI tone; not narration
├── scripts/
│   └── gemini_smoke_test.py      # opt-in external smoke-test entrypoint
├── src/
│   ├── story_finder.py           # discovery executable and compatibility surface
│   ├── process_stories.py        # pipeline executable and compatibility surface
│   └── pyonpyin/
│       ├── core.py               # shared policy, validation, IDs, utilities
│       ├── web_app.py            # Flask routes, admin/public API, legacy HTML, SPA host
│       ├── sheets.py             # Google Sheets repository adapter
│       ├── gemini.py             # Gemini provider/client boundary
│       └── audio.py              # TTS adapter boundary (synthesis not verified)
└── tests/
    └── test_workflow.py          # offline Python policy, API and workflow tests
```

The root executable paths are still used by README instructions and the
existing Actions workflows. Keep them stable until compatibility entrypoints
and all callers have been deliberately migrated.

## Applications and request boundaries

| Area | Current location / entrypoint | Verified boundary and limitation |
| --- | --- | --- |
| Public website | `frontend/src/App.tsx`: `/`, `/stories`, `/stories/:storyId`; Flask public routes `/` and `/story/<id>` | React reads only `/api/stories`, which applies publication checks. Demo fixtures are enabled only in explicit demo mode and labelled. Flask also retains a separate legacy server-rendered public page. |
| Admin dashboard | Same React application: `/admin/*`; Vite host `/admin/app/` | Admin APIs are under `/api/admin/*` and require the current Flask password session. Mutations use CSRF tokens. React admin routes are not a separately built bundle or separately hosted app. Flask retains a legacy `/admin` interface as well. |
| Backend API | `src/pyonpyin/web_app.py`, imported as `pyonpyin.web_app:app` | One Flask module owns public/admin APIs, route-level authorization, SPA asset hosting, health, and legacy HTML/form endpoints. The public API is distinct by URL and data policy, but not a separate process/service. |
| Discovery | `src/story_finder.py` -> `story_finder.main()` | Can run as a scheduled/manual GitHub Actions job. Reads approved source configuration; may write Sheets when credentials are supplied. |
| AI processing | `src/process_stories.py` -> `process_stories.main()` | Separate scheduled/manual Actions job; opt-in Gemini, one story per run, policy/rights gated. Dashboard dispatch is separately gated; no live run was made. |
| Shared policy/models | `src/pyonpyin/core.py` and Google Sheet row dictionaries | Shared validation and IDs live in `core.py`; records are untyped row dictionaries, not a versioned standalone shared package or schema service. |
| Audio | `src/pyonpyin/audio.py`; browser-only demo component in `frontend/src/DemoAudioPlayer.tsx` | Server adapter intentionally does not synthesize; no verified Burmese voice or secure audio storage. Browser tone is explicitly not story audio. |
| Persistence | `src/pyonpyin/sheets.py` | Google Sheets is the initial repository/control center. No live spreadsheet was read or changed. It is not a transactional job queue. |
| Tests | `tests/test_workflow.py`, `frontend/src/*.test.ts(x)` | Offline tests mock provider and store boundaries. Live external acceptance tests are separate and were not run. |
| Deployment | `Dockerfile`, Flask/Gunicorn and Vite build | One image builds the SPA and serves it from Flask. Docker availability/build was not verified in this environment. |

### React and Flask routes

- React public: `/#/`, `/#/stories`, `/#/stories/:storyId`.
- React admin: `/#/admin` and admin subroutes, reached from `/admin/app/`.
- Flask admin APIs: `/api/admin/login`, `/logout`, `/overview`, `/jobs`,
  `/jobs/dispatch`, and `/story/<id>` operations.
- Flask public API: `/api/stories`; health: `/health`.
- Flask legacy templates/forms remain at `/`, `/story/<id>`, `/admin`, and
  other `/admin/story/...` routes. These are compatibility surfaces, not a
  second modern React application.

The root path and `/admin` therefore remain legacy Flask pages; the modern
React experience currently lives at `/app/` and `/admin/app/`. Route changes
should be a separately tested compatibility task, not an incidental folder
move.

## Dependencies and configuration

- Frontend runtime: React 18, React DOM 18, React Router 6, Lucide icons.
- Frontend tooling: Vite 5, TypeScript 5.7, Vitest 2, Testing Library, jsdom.
  There is no animation or component-framework dependency.
- Backend: Flask 3, Google API client/auth libraries; Gunicorn on non-Windows.
- CI/runtime: Python 3.12 GitHub Actions and Dockerfile toolchain.
- Secrets are server/Actions-side, never Vite `VITE_*` values:
  `PYONPYIN_ADMIN_PASSWORD`, `PYONPYIN_SESSION_SECRET`,
  `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_TOKEN_JSON` or `GOOGLE_TOKEN_FILE`,
  `GEMINI_API_KEY`, optional `PYONPYIN_GITHUB_TOKEN`,
  `GOOGLE_TTS_API_KEY` (adapter unavailable/unverified).
- Non-secret settings include `GOOGLE_SPREADSHEET_ID`, `GEMINI_MODEL`,
  `PYONPYIN_GEMINI_AUTOMATION_ENABLED`, `PYONPYIN_GITHUB_DISPATCH_ENABLED`,
  `PYONPYIN_GITHUB_REPOSITORY`, `PYONPYIN_GITHUB_REF`,
  `PYONPYIN_PUBLISHING_ENABLED`, `PUBLIC_BASE_URL`, `PYONPYIN_HTTPS`,
  `TTS_PROVIDER`, `GOOGLE_TTS_VOICE`, `AUDIO_OUTPUT_DIR`, `HOST`, `PORT`.
  See [SETUP_AND_SECRETS.md](./SETUP_AND_SECRETS.md) for setup and safety
  semantics. Do not enable provider flags without authorization.

## What already works independently

- `story_finder.py` and `process_stories.py` are separate command/Actions
  entrypoints and can run without the web process. Discovery can dry-run when
  Sheets credentials are absent; processing is disabled unless explicitly
  enabled. Real Sheet/Gemini behavior still needs authorized acceptance tests.
- The Vite app can build and run as a development server. Demo mode lets the
  public and admin interfaces be explored without Sheets or Gemini.
- Flask can run independently and serves health, public pages/API, authenticated
  admin APIs and, after a build, the React assets.
- Audio has a module boundary, but there is no working production synthesis.
- Publishing checks exist but remain disabled by default.

“Can be run as a process” does not mean “is production-ready or independently
deployable.” Google Sheets, credentials, common Flask session/CSRF behavior,
static-asset hosting and workflow configuration still couple the components.

## Safest useful architecture now

Retain the current repository layout and establish explicit logical ownership:

```text
frontend/                 # single SPA: public routes + private admin routes
src/pyonpyin/web_app.py   # Flask API + compatibility pages + SPA serving
src/story_finder.py       # stable discovery entrypoint
src/process_stories.py    # stable generation entrypoint
src/pyonpyin/core.py      # shared policy and utilities
src/pyonpyin/sheets.py    # persistence adapter
src/pyonpyin/gemini.py    # model provider boundary
src/pyonpyin/audio.py     # TTS provider boundary
tests/                    # backend and frontend offline suites
docs/                     # operational and architecture docs
.github/workflows/        # independent discovery, generation and CI jobs
```

Do not create empty `apps/` or `packages/` directories to imply separation.
Do not move the root scripts yet: tests and external workflow/README commands
patch and invoke those module paths. Do not split Flask routes into blueprints
until route contracts, app construction, and tests can be migrated together.
The current layout has the least deployment and data migration risk.

## Staged migration path

1. **Now — document and test boundaries.** Keep SPA public/admin layouts,
   public-only story API, authenticated/CSRF-protected admin API, pipeline
   commands, and provider adapters as they stand. Add route and contract tests
   when behavior changes. No data migration is required.
2. **Next — modularize Flask behind compatibility imports.** Introduce an app
   factory and blueprints in a dedicated API package, one route group at a time.
   Preserve `pyonpyin.web_app:app` as the WSGI entrypoint and preserve all
   legacy routes until callers move. Verify authentication, CSRF, public
   filtering and templates in offline tests before changing deployment.
3. **Next — separate frontend source modules, not deployables.** Extract public
   and admin route/layout components while sharing the typed API client and UI
   primitives. Preserve route paths, HashRouter behavior, demo mode and tests.
   Keep a single Vite build until module boundaries are exercised by tests.
4. **Private preview — deploy one same-origin service first.** Build Vite assets
   and serve Flask behind HTTPS/reverse proxy. Keep `/api/admin/*` protected,
   publishing and workflow dispatch off by default, and demo mode explicit.
   This is safer than cross-origin cookies/CORS/CSRF configuration.
5. **Only when operationally justified — split frontend hosting.** Publish the
   static frontend separately only after same-origin API routing or an explicit
   credentialed CORS + cookie + CSRF threat model is implemented and tested.
   Public and admin may then become separate builds/origins, with admin
   additionally protected by an identity/access layer. Do not put secrets in
   either static bundle.
6. **Before scaling the pipeline — replace Sheets job claiming.** Move queue
   locking/idempotency to a transactional store before multiple web/worker
   replicas or dependable dispatch guarantees. Preserve Sheets as a control
   center via a deliberate adapter/migration plan.
7. **Before audio launch — verify a Burmese TTS provider and storage.** Keep the
   interface disabled until provider voice support, cost, audio bytes, secure
   object storage, reviewer access and output quality are verified.

## Preview security and launch gates

- Use private hosting/access controls for preview; HTTPS; strong unique admin
  password and stable secret key; secure cookies; backups and logs.
- Keep `PYONPYIN_PUBLISHING_ENABLED=false`,
  `PYONPYIN_GEMINI_AUTOMATION_ENABLED=false`, and
  `PYONPYIN_GITHUB_DISPATCH_ENABLED=false` until separately authorized.
- Do not use production Sheet credentials for an unverified preview. Prefer a
  copied/test spreadsheet with restricted service-account access.
- Do not expose Flask admin or legacy form routes publicly without assessing
  shared-password auth, rate limiting, CSRF, proxy trust and session handling.
- Before public launch, add individual admin identities/MFA or an access proxy,
  rate limits, audit/backup/restore and alerting; verify dependency, provider,
  storage and recovery behavior; independently test public output and publishing
  safeguards.
- No deployment, live external requests, paid service use, workflow dispatch,
  commit or push is performed by this architecture change.
