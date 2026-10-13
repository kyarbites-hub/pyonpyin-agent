# PyonPyin AI Agent MVP Implementation Plan

## Audit snapshot

Audit date: 2026-10-13. The working tree was already modified before this work;
those changes are preserved. The repository contains a Python Story Finder,
Google Sheets-backed workflow, Gemini REST client, Flask application, and a
React/TypeScript/Vite application. Baseline offline backend tests and frontend
tests/build passed before this implementation.

| Area | Verified in repository | Not verified / limitation |
| --- | --- | --- |
| Discovery | HTTPS Atom/RSS fetch, stable IDs, URL deduplication, per-cycle category caps, source allowlist, additive Sheets tabs | No live feed or Sheet was accessed during this audit |
| Rights | Exact rights evidence and category gates for source use; unknown-rights theme-only generation omits source identifiers/text | Work-level legal conclusions still need a qualified human reviewer |
| Generation | Gemini REST adapter validates structured output, episode continuity, quizzes, reflection, and transient errors; automation is opt-in | No live Gemini request or quota/billing verification |
| Persistence | Six Google Sheets tabs, idempotent key upserts, segmented text, additive schema changes | No real spreadsheet permission or write test; Sheets remains the production store and concurrency boundary |
| Backend | Flask session authentication, admin API, CSRF checks, security headers, public publication gates | No external identity provider or persistent job queue; long tasks run through scheduled/manual GitHub Actions |
| Frontend | Separate React public/admin routes and layouts, responsive demo mode, typed Flask API client, live rights review and gated one-story workflow dispatch | Both experiences are one SPA; some workflow pages remain demo-only; no separate frontend deployables |
| Audio | Modular provider boundary and status metadata | Current Google Cloud adapter intentionally refuses synthesis; no verified Burmese voice or real audio asset |
| Publishing | Disabled by default; explicit rights/content/approval checks; published-only public API | Enabling publication changes content visibility and requires separate owner authorization; not enabled here |
| Deployment | Python dependencies support Gunicorn; Dockerfile builds Vite and Flask serves its output | No container build, deployment, or live health check was verified |

## Prioritized roadmap and status

1. **P0 — Protect working integrations and public output (implemented).**
   The frontend now passes the in-memory server-issued CSRF token on draft-save
   and content-review API mutations. Published public API output suppresses
   episode audio references unless that episode's status is READY. Offline
   regression tests cover both behaviors.
2. **P0 — Reproducible setup and deployment (implemented, not deployed).**
   Provide secret-free setup, test, and deployment guides and a container build
   that compiles the frontend and runs the existing Flask app behind a
   production WSGI server. Do not deploy it.
3. **P1 — Connect the remaining admin workflows (partially implemented).**
   The React rights workspace now saves explicit category, rights evidence,
   reviewer, jurisdiction, and individual permission decisions through an
   authenticated CSRF-protected API. The production queue now offers an
   explicit, CSRF-protected one-story GitHub Actions dispatch when separately
   enabled, configured, and confirmed by an admin. Provider-backed audio
   review remains unavailable. Never expose GitHub credentials in the browser.
4. **P1 — Durable job execution and Sheet concurrency (remaining).**
   Add a durable job/idempotency mechanism before accepting dashboard-triggered
   long-running work. Google Sheets read-then-upsert is not a transactional
   lock; scheduled workflows currently provide the only coarse concurrency
   protection.
5. **P1 — Provider-backed Burmese audio (blocked on provider/voice validation).**
   Confirm a provider/voice and its pricing/terms with current official
   documentation and a Myanmar-language reviewer. Implement server-side
   synthesis, verified file storage, authenticated review/download, and tests.
   Until then, audio remains blocked/explicitly unavailable.
6. **P2 — Release hardening (remaining).**
   Add deployment-specific HTTPS, backup/restore, monitoring, rate limiting,
   secret rotation, and external-service acceptance checks before public use.

## Target architecture

- Keep the current repository as a modular monolith for the initial private
  preview. See [ARCHITECTURE.md](./ARCHITECTURE.md) for the audited module
  map, route boundaries, and staged extraction plan.
- Keep `src/story_finder.py`, `src/process_stories.py`, and
  `src/pyonpyin/` as the single automation/backend implementation. The
  top-level scripts remain stable workflow and test compatibility entrypoints.
- Keep Google Sheets as the initial store and control center. Do not migrate or
  rename tabs without a separately approved migration.
- Flask provides same-origin public and authenticated admin APIs and currently
  serves the built React bundle. Public and admin routes share one React/Vite
  build, but admin APIs require the existing cookie-backed session and CSRF
  tokens remain in runtime memory.
- GitHub Actions performs scheduled discovery and optional one-draft
  processing. An optional admin dispatch uses a server-side GitHub token,
  queued-story eligibility checks, and a `DISPATCHED` marker. Google Sheets
  has no atomic compare-and-swap; this guards normal duplicate requests but
  cannot claim transactional idempotency.
- Public records must have a `PUBLISHED` history row and pass the current
  rights, explicit approval, category, episode-continuity, and required-audio
  gates. Publishing stays disabled by default.

## Working-tree file scope

- `src/pyonpyin/web_app.py`: add explicit-evidence rights review and strip
  episode audio references from public API payloads unless audio status is
  READY.
- `frontend/src/api.ts` and `frontend/src/App.tsx`: pass same-origin CSRF token
  on draft, content-review, and rights-review operations.
- `tests/test_workflow.py` and `frontend/src/api.test.ts`: offline regression
  coverage.
- `README.md`, `docs/MVP_IMPLEMENTATION_PLAN.md`,
  `docs/SETUP_AND_SECRETS.md`, `docs/DEPLOYMENT.md`,
  `docs/TESTING.md`: accurate setup and acceptance guidance.
- `Dockerfile`, `.dockerignore`: local/container build configuration only.

## Acceptance gates

- Offline Python and frontend tests, TypeScript/Vite production build, syntax
  checks, and `git diff --check` pass.
- Mocked tests prove admin mutations send CSRF tokens and public responses
  suppress unready audio.
- No live Sheet, Gemini, TTS, publication, deployment, or paid service request
  is made as part of implementation.
- Google Sheets, Gemini, Burmese TTS, and public deployment remain explicitly
  marked unverified until tested with authorized credentials and permission.
