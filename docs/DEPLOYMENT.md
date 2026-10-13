# Deployment readiness

No public deployment is configured or performed. This repository now includes
a Docker build definition for evaluation and private staging; deployment still
requires owner approval and real credentials.

The current safe topology is one Flask/Gunicorn service serving its API and
the built React SPA from the same origin. Public and admin are different
routes/layouts, not independently deployable frontend applications. The
discovery and generation jobs are separate GitHub Actions workers. See
[ARCHITECTURE.md](./ARCHITECTURE.md) for the staged split plan.

The runtime image runs as an unprivileged user and exits at startup unless
both admin credentials are configured. Publishing, Gemini automation, and
GitHub dispatch default to disabled in the image and application. Keep those
settings disabled for a preview.

Scheduled discovery and processing triggers are removed from the local
workflow definitions for this preview preparation. Manual workflow dispatch
remains an explicit operator action. These local edits do not alter workflows
already present on GitHub; pause the existing scheduled workflows in the
repository's Actions settings before any preview rollout.

## Container build and run

From the repository root:

```powershell
docker build --build-arg VITE_DEMO_MODE=true -t pyonpyin-agent-preview .
docker run --rm -p 8000:8000 `
  -e PYONPYIN_ADMIN_PASSWORD="use-a-unique-secret" `
  -e PYONPYIN_SESSION_SECRET="use-a-long-random-secret" `
  -e PYONPYIN_HTTPS=true `
  -e PYONPYIN_PUBLISHING_ENABLED=false `
  pyonpyin-agent-preview
```

Do not paste real credentials into shell history in a production environment.
Use your host's secret manager or a restricted local secret file instead. The
container health endpoint is `/health`; the React app is served at `/app/` and
`/admin/app/` by Flask. The existing public Flask pages and published-only API
remain on `/` and `/api/stories`.

This command builds the frontend with visibly labeled demo fixtures. The
backend still requires server-side admin credentials, but no Sheets, Gemini,
or TTS credentials are needed for this UI-only preview. Protect it with the
hosting provider's private access control. To build a real-data bundle, use
`docker build --build-arg VITE_DEMO_MODE=false -t pyonpyin-agent .` and provide
Google Sheets credentials to the runtime through the host's secret manager.
The React API calls are same-origin, so no credentialed CORS setup is needed.
Never provide backend credentials as `VITE_*` variables. Demo content is not
published content and must not be presented as real stories.

## Production host requirements

- Run the image behind a managed HTTPS reverse proxy/load balancer; set
  `PYONPYIN_HTTPS=true`.
- Restrict the preview at the hosting/access-proxy layer. The current Flask
  admin uses one shared password rather than individual identities or MFA;
  do not expose it as an unrestricted public admin service.
- Set a stable, randomly generated `PYONPYIN_SESSION_SECRET`, strong
  `PYONPYIN_ADMIN_PASSWORD`, and `PYONPYIN_PUBLISHING_ENABLED=false`.
- Inject the Sheets service account JSON as a secret and share only the
  intended spreadsheet with that service account.
- Configure outbound HTTPS to Google APIs. Never mount `token.json` in the
  frontend or image.
- Google Sheets is the persistent control center. The container filesystem is
  not a persistent audio store; no real TTS audio is currently generated.
- Keep `PYONPYIN_PUBLISHING_ENABLED=false`,
  `PYONPYIN_GEMINI_AUTOMATION_ENABLED=false`, and
  `PYONPYIN_GITHUB_DISPATCH_ENABLED=false` for a UI-only private preview. Use
  explicit sandbox credentials if backend integration testing is separately
  authorized.
- Store logs in the host's log service. Set alerts for health failures,
  workflow failure notifications, and repeated processing errors. Maintain
  access-controlled spreadsheet backups before schema or publishing changes.

## Scheduling and cost

The existing GitHub Actions workflows are the scheduler for discovery and
optional processing. They use repository secrets/variables and have
concurrency groups; Gemini processing remains off unless explicitly enabled.
GitHub schedule execution can be delayed and is not a guaranteed publication
cadence. An optional dashboard dispatch is now implemented behind separate
server-side GitHub-dispatch and Gemini opt-in flags. It only requests one
eligible queued story and never publishes. Dispatch acceptance is not
generation success. Google Sheets does not support an atomic claim operation,
so this is not a transactional distributed lock; investigate `DISPATCH_UNKNOWN`
in Actions before retrying. The admin API also rejects a second dispatch while
another record is marked `DISPATCHED` or `GENERATING`.

This setup has no newly introduced paid service. Google Sheets/Cloud, Gemini,
the hosting provider, and any future TTS service have provider-specific quotas
and may incur costs. Check current pricing and free-tier limits before enabling
them. Free hosting plans may sleep, limit runtime/build minutes, or have
ephemeral filesystems; availability and terms change. No cost estimate can be
verified without selecting a provider and plan.

## Before public release

1. Complete current service pricing/terms review and authorized live
   Google/Gemini/TTS acceptance tests.
2. Select persistent audio/object storage if narration is added.
3. Replace Google Sheets read/upsert job claiming with a durable transactional
   queue before treating dashboard dispatch as duplicate-proof.
4. Put admin behind a private access layer or add individual accounts, MFA,
   and rate limits.
5. Confirm HTTPS, backups, restore procedures, logging, and incident contacts.
6. Keep publication disabled until the owner explicitly authorizes it and the
   final approval flow is independently tested.
7. If hosting the React bundle on a separate origin, implement and test
   credentialed CORS, cookie SameSite/Secure settings, CSRF and origin
   validation first. Do not assume the current same-origin API client supports
   that topology.
