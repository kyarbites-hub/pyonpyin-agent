# Testing and verification

## Offline tests

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
python -B -m unittest discover -s tests -v
Set-Location frontend
npm ci
npm test
npm run build
Set-Location ..
git diff --check
```

Backend tests use fake stores, HTTP responses, and fixtures. Frontend tests use
demo fixtures and mocked browser APIs. They must not write to a live Sheet,
call Gemini/TTS, or publish.

## Scope of local verification

- Rights gates, category non-inference, deduplication, theme-only prompt
  privacy, Gemini response validation, Sheets serialization and mocked
  batch-upsert behavior (duplicate input keys coalesce; omitted existing
  columns are preserved), Flask
  authentication/CSRF, explicit rights-review validation, gated GitHub
  dispatch with mocked responses, approval gates,
  suppression of unready public audio, public response filtering, and selected
  frontend interactions have offline test coverage.
- The production frontend build type-checks and emits assets served by Flask.
- The Flask API and Vite development server use the same-origin `/api` proxy
  when configured for non-demo mode. Frontend tests verify CSRF headers on
  state-changing requests; no real Google Sheet end-to-end request was made.

## External acceptance tests still required

These tests need owner-provided credentials/permissions and must be separately
authorized:

- Google Sheets schema initialization, service-account permissions, read/write
  behavior, duplicate reruns, quotas, and concurrent workflow execution.
- Gemini quota, policy/terms, actual Burmese text quality, and cost.
- A verified Burmese TTS voice, actual audio bytes, secure storage and playback,
  pronunciation review, and cost.
- HTTPS deployment health, persistence, backups, recovery, and authorization
  from outside the local environment.

The optional Gemini GitHub workflow performs one live request only when its
manual input is explicitly selected. Do not enable it as part of routine
offline tests.
