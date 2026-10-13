# Setup and secrets

This project does not include credentials. Use environment variables or your
deployment provider's secret store. Never add credentials to `.env.example`,
the frontend, a commit, or browser storage.

## Owner checklist

- [ ] Install Python 3.12+ and Node.js 20+.
- [ ] Decide whether to enable Google Sheets access and grant the service
  account access to the intended spreadsheet.
- [ ] Store the admin password and session secret outside the repository.
- [ ] Keep Gemini automation and publishing disabled until their separate
  authorization steps are complete.
- [ ] Verify an actual Burmese TTS voice, its price, and pronunciation before
  enabling audio.
- [ ] Back up the spreadsheet before running schema initialization against
  production data.

## Local Windows setup

1. Install Python 3.12+ and Node.js 20+.
2. From the repository root, install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   Set-Location frontend
   npm ci
   Set-Location ..
   ```

3. Configure server-only environment variables in the PowerShell session:

   ```powershell
   $env:PYTHONPATH = (Join-Path (Get-Location) "src")
   $env:PYONPYIN_ADMIN_PASSWORD = Read-Host "Local admin password"
   $env:PYONPYIN_SESSION_SECRET = (& python -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
   $env:PYONPYIN_PUBLISHING_ENABLED = "false"
   ```

4. Start Flask in one terminal:

   ```powershell
   python -m pyonpyin.web_app
   ```

5. In a second terminal, run the frontend:

   ```powershell
   Set-Location frontend
   Copy-Item .env.example .env.local
   npm run dev
   ```

   Open `http://127.0.0.1:5173/`. Demo mode is enabled by the placeholder
   frontend variable and makes no Sheet or Gemini requests. Demo actions are
   browser-local only.

## Optional Google Sheets access

- Enable Google Sheets API in a Google Cloud project.
- Create a service account, share the target spreadsheet with its email, and
  grant only the spreadsheet access required by the application.
- Set `GOOGLE_SPREADSHEET_ID` and either
  `GOOGLE_SERVICE_ACCOUNT_JSON` (JSON content) or `GOOGLE_TOKEN_FILE` (local
  authorized-user token path). The service-account setting takes precedence.
- The application adds missing tabs/headers without clearing existing data.
  Schema initialization writes to Sheets; do not run it against a live sheet
  until access and backup are approved.

No live Google access is performed by automated tests.

## Optional Gemini access

- Create an API key only after reviewing the provider's current terms, quota,
  and price.
- Set `GEMINI_API_KEY` server-side and optionally `GEMINI_MODEL`.
- Keep `PYONPYIN_GEMINI_AUTOMATION_ENABLED=false` unless an operator has
  deliberately enabled and authorized generation. Do not add either value as a
  `VITE_` frontend variable.
- For source-based generation, first complete work-level rights review and
  evidence. Unknown-rights jobs must remain theme-only.

The project has an explicit opt-in live smoke workflow. It was not run here.

## Optional dashboard-triggered processing

The admin production queue can dispatch one specifically selected, already
queued story to the existing GitHub Actions workflow. It does not run Gemini
inside Flask, and acceptance means only that GitHub accepted a workflow
dispatch—not that generation completed. The workflow still requires the
repository variable `PYONPYIN_GEMINI_AUTOMATION_ENABLED=true` and the
`GEMINI_API_KEY` secret. It forces publishing off.

To enable this feature deliberately, configure these values only in the Flask
server's protected environment/secret store:

- `PYONPYIN_GITHUB_DISPATCH_ENABLED=true`
- `PYONPYIN_GEMINI_AUTOMATION_ENABLED=true`
- `PYONPYIN_GITHUB_TOKEN`: fine-grained GitHub token restricted to this
  repository, with Actions write permission; never expose it to the browser.
- `PYONPYIN_GITHUB_REPOSITORY=owner/repository`
- `PYONPYIN_GITHUB_REF`: a trusted branch/ref containing the workflow
  (defaults to `main`).

Also configure the GitHub Actions repository variable and secrets listed
above. The admin operator must review story rights/category first, queue an
eligible record, then explicitly select and confirm dispatch in the dashboard.
Do not enable until Gemini pricing/quota and token access have been approved.
If the dispatch response times out, the record is marked
`DISPATCH_UNKNOWN`; inspect the repository's Actions page before any manual
reconciliation or retry to avoid duplicate runs. Google Sheets does not provide
an atomic compare-and-swap, so this is guarded against ordinary repeated
requests but is not a transactional distributed lock.

## Admin and publishing controls

- `PYONPYIN_ADMIN_PASSWORD`: required admin password.
- `PYONPYIN_SESSION_SECRET`: unique random signing secret; keep it stable across
  replicas and rotate deliberately.
- `PYONPYIN_HTTPS=true`: set only when HTTPS terminates in front of Flask so
  session cookies are Secure.
- `PYONPYIN_PUBLISHING_ENABLED=false`: keep false until a separate, explicit
  publishing authorization and complete policy review.
- `PUBLIC_BASE_URL`: canonical HTTPS base URL, required only if publishing is
  intentionally enabled.

The current app uses a single shared admin password, not per-user accounts,
MFA, or role-based authorization. Do not expose the admin interface publicly
without an additional access-control review.

## Audio provider

`TTS_PROVIDER` is unset by default. The existing adapter does not synthesize
audio and reports provider unavailability. Do not set audio status to READY
unless a provider has been verified, synthesis has produced a non-empty audio
file, the file is stored securely, and a Myanmar-language reviewer has checked
the output.
