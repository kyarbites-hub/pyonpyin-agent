# PyonPyin AI Story Platform

PyonPyin is a Python-based story discovery and review workflow. It keeps Google
Sheets as the control center, prepares safe Myanmar-language story drafts with
Gemini, and provides an authenticated admin dashboard plus a public
catalogue. The system does not auto-publish: publication is disabled unless an
operator deliberately enables it, and each story still needs explicit human
approval.

## Current features and limitations

- Discovery reads only sources marked `APPROVED` and `automation_allowed: true`
  in `data/approved_sources.json`. Source approval does not approve the rights
  for any individual work.
- Atom and RSS feeds are supported. Feed requests are HTTPS-only, bounded to
  5 MiB, and retried at most three times for transient errors.
- Story IDs are deterministic. Feed URLs and IDs are compared with existing
  library rows and the legacy `SourceQueue` before saving.
- Candidate limits are five `CHILDREN`, five `ADULT`, and five
  `UNCLASSIFIED` stories per discovery run. Category is taken only from explicit
  feed metadata, a configured category mapping, or a human-approved source
  default. Unknown category is not guessed.
- The currently configured Standard Ebooks feed does not provide verified
  children/adult classifications or a configured source-level rights policy.
  Candidates without an explicit category are saved but not queued. With an
  explicit audience category, works of unknown rights can continue as
  independent theme-based originals without a per-work copyright review.
  Source-based retelling still requires the explicit verified policy below.
  The configured pending sources are not crawled.
- Google Sheets has six platform tabs: **Story Library**, **Story Production**,
  **Story Text**, **Story Episodes**, **Processing History**, and
  **Publishing History**. They implement three logical areas: Library;
  Production (including text, episode, and processing-history subtabs); and
  Publishing History.
  Existing tabs and values are retained; new tabs/headers are added
  non-destructively. The legacy `SourceQueue` is still populated for compatible
  existing workflows.
- Unknown-rights candidates with an explicit CHILDREN or ADULT category can be
  automatically queued for a theme-only original. Gemini receives only the
  category and an allowlisted broad theme, never the discovered title, author,
  URL, or source text. Unknown rights remain uncleared and do not imply
  publication permission.
- Source-based retellings require an explicit `VERIFIED_PUBLIC_DOMAIN` source
  policy with evidence, jurisdiction, reviewer, and translation/AI permissions.
  The feed must provide the source text, which discovery reads only in this
  verified mode. Missing or invalid policy falls back to theme-only generation.
  Existing production rows are reused and never overwritten. Gemini runs are
  opt-in, handle at most one draft per run, and retry transient failures once.
  Generated content always remains a draft for human review.
- Text exceeding 40,000 characters is split into ordered **Story Text**
  segments to stay below Google Sheets' per-cell size limit. Gemini processing
  is bounded to 200,000 source/story characters and 100 episodes; each episode
  is limited to 40,000 characters.
- The admin interface supports rights review, category assignment, selection,
  Myanmar text and episode editing, audio references, processing status,
  publishing history, and explicit approval. It uses a password-protected
  session and CSRF tokens.
- The public site and `/api/stories` expose only records with a successful
  publication-history entry and passing rights/content/episode checks.
- A Google Cloud TTS adapter is present but deliberately cannot synthesize
  audio yet. The currently reviewed official voice-catalogue overview does not
  verify a usable Burmese `my-MM` voice. Do not mark audio ready until voice
  support and pronunciation have been independently verified.

## Configuration

### Google Sheets

1. In Google Cloud Console, create/select a project and enable the Google
   Sheets API.
2. Create a service account and a JSON key. Share the existing spreadsheet with
   the service account email as an Editor. The ID is the part of its URL between
   `/d/` and `/edit`.
3. Set the following environment variables locally, or GitHub repository
   secrets/variables:

   - `GOOGLE_SPREADSHEET_ID` — repository variable (not a credential).
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — service-account JSON, stored as a secret.
   - For local OAuth, `GOOGLE_TOKEN_FILE` — path to the existing authorized-user
     `token.json` file. Alternatively, `GOOGLE_TOKEN_JSON` may contain its JSON
     text; the file path itself is not a valid `GOOGLE_TOKEN_JSON` value.

   The existing `GOOGLE_TOKEN_JSON` OAuth user-token secret remains supported
   for compatibility; the service-account credential takes precedence when
   both it and the service-account credential are set. `GOOGLE_TOKEN_JSON`
   takes precedence over `GOOGLE_TOKEN_FILE`. Never commit credentials.
4. On the first successful discovery or admin-dashboard request, the
   application creates the new tabs and adds missing columns to their header
   rows. It does not clear existing data or rename `SourceQueue`.

### Gemini

Create an API key in Google AI Studio and set:

- `GEMINI_API_KEY` — secret.
- `GEMINI_MODEL` — optional model name; defaults to `gemini-2.5-flash`.

Gemini free-tier access is limited to eligible models and quotas, which Google
can change. Review [current Gemini API pricing and terms](https://ai.google.dev/gemini-api/docs/pricing)
before use; free-tier data may be handled under different terms than paid-tier
data. This repository does not enforce a provider-side free quota. Theme-only
requests contain no discovered work text or identifying book metadata;
source-based requests require the verified policy. Automation is disabled
unless `PYONPYIN_GEMINI_AUTOMATION_ENABLED=true`; check billing/quota before
opting in. Each run processes at most one draft and retries temporary errors
once.

### Admin dashboard

Set these environment values. Use generated, unique secrets/passwords and a
TLS-terminating host for any remotely accessible deployment:

- `PYONPYIN_ADMIN_PASSWORD` — required to enable login.
- `PYONPYIN_SESSION_SECRET` — a long random session-signing secret.
- `PYONPYIN_PUBLISHING_ENABLED` — defaults to `false`; only set to `true` after
  private deployment setup. It does not override any story-level review gates.
- `PUBLIC_BASE_URL` — canonical HTTPS site URL, required before publication
  (for example, `https://stories.example.org`). Public links are never built
  from an untrusted request `Host` header.
- `PYONPYIN_HTTPS=true` — set when the app is served behind HTTPS so session
  cookies are marked secure.
- `HOST` and `PORT` — optional local bind configuration; defaults to
  `127.0.0.1:8000`.

### Text-to-speech

`TTS_PROVIDER` is unset by default. The Google Cloud adapter requires
`GOOGLE_TTS_API_KEY` and `GOOGLE_TTS_VOICE` beginning with `my-MM-`, but it
currently returns “not verified” instead of making a potentially billable
request. The official [Google Cloud voice documentation](https://cloud.google.com/text-to-speech/docs/voices)
does not currently establish an approved Burmese narration path in this
project. **Single remaining setup step:** select and verify a Myanmar-capable
TTS provider/voice, including its price and pronunciation with a Myanmar
speaker, before enabling synthesis. There is no configured free provider now.
Until that verification is completed and an adapter is implemented, production
records remain `WAITING_PROVIDER_VERIFICATION`; required audio blocks
publication. No paid TTS request is made by this code.

## Local setup (Windows PowerShell)

Fast path from the repository root (set Sheets variables/credentials first):

```powershell
$env:PYTHONPATH = "src"
python -m pip install -r requirements.txt
python src\story_finder.py
```

Set `GOOGLE_SPREADSHEET_ID` and either `GOOGLE_TOKEN_FILE` (local) or
`GOOGLE_SERVICE_ACCOUNT_JSON` (Actions). The finder is idempotent. To generate
one draft, after confirming quota/billing, set
`PYONPYIN_GEMINI_AUTOMATION_ENABLED=true` and `GEMINI_API_KEY`, then run
`python src\process_stories.py`. Leave the automation variable unset/false to
avoid all Gemini requests. Publishing remains disabled.

Offline verification:

```powershell
$env:PYTHONPATH = "src"
python -B -m unittest discover -s tests -v
```

To run discovery in dry-run mode, leave Sheets credentials unset:

```powershell
$env:PYTHONPATH = "src"
python src\story_finder.py
```

To run the admin/public application locally, set Sheets credentials and the
dashboard password first:

```powershell
$env:PYTHONPATH = "src"
$env:GOOGLE_SPREADSHEET_ID = "your-spreadsheet-id"
$env:GOOGLE_TOKEN_FILE = "C:\path\to\token.json"
$env:PYONPYIN_ADMIN_PASSWORD = "use-a-unique-local-password"
$env:PYONPYIN_SESSION_SECRET = "use-a-long-random-local-secret"
python -m pyonpyin.web_app
```

For service-account authentication instead, set
`GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content C:\secure\service-account.json -Raw`
and leave `GOOGLE_TOKEN_FILE` unset. Service-account credentials take
precedence if both credential methods are configured.

Open `http://127.0.0.1:8000/` for the public site or
`http://127.0.0.1:8000/admin/login` for the admin login. Keep credential JSON
outside the repository; the example filename above is only illustrative.

The processing job is opt-in because Gemini requests may use quota or incur
charges. To enable local processing, first verify the selected model and
account limits, then set:

```powershell
$env:PYONPYIN_GEMINI_AUTOMATION_ENABLED = "true"
$env:GEMINI_API_KEY = "your-key-from-a-secure-secret-store"
python src\process_stories.py
```

The processor reads `QUEUED` rows, processes no more than one per run, and
rechecks policy. Unknown rights use an independent theme-only prompt that
excludes the discovered title and source text. Verified public-domain mode
requires the policy below and feed-provided text. It saves errors/drafts and
does not publish. Audio remains pending until the TTS setup step above is
complete.

For local OAuth discovery and draft processing, set the same spreadsheet/token
environment used by the dashboard, for example:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
$env:GOOGLE_SPREADSHEET_ID = "your-spreadsheet-id"
$env:GOOGLE_TOKEN_FILE = "C:\path\to\token.json"
$env:PYONPYIN_PUBLISHING_ENABLED = "false"
python src\story_finder.py
```

Automatic theme-only generation requires a known audience category; unknown
categories remain in the library until a source-level category mapping or
default is explicitly configured. The finder queues new eligible drafts
idempotently and does not overwrite any existing production row.

## GitHub Actions

Add `GOOGLE_SERVICE_ACCOUNT_JSON` to repository **Secrets** and
`GOOGLE_SPREADSHEET_ID` to repository **Variables**. Set `GEMINI_API_KEY` as a
secret and optionally `GEMINI_MODEL` as a variable.
The processing workflow passes `secrets.GEMINI_API_KEY` to Python through its
environment. It does not call Gemini unless the repository variable
`PYONPYIN_GEMINI_AUTOMATION_ENABLED` is exactly `true`; when opted in, a missing
key produces a non-secret error. GitHub does not reveal stored secret values
through repository inspection. Publishing is explicitly disabled in the job.

For a source where **every work** has been verified public domain for the
intended jurisdiction, its entry in `data/approved_sources.json` may specify:

```json
"rights_policy": {
  "mode": "VERIFIED_PUBLIC_DOMAIN",
  "all_works_verified": true,
  "evidence": "URL or description of the rights review",
  "jurisdiction": "Myanmar",
  "reviewer": "Authorized reviewer",
  "translation_permission": "YES",
  "ai_processing_permission": "YES"
}
```

Do not configure this from the source's general reputation or a different
country's public-domain status. A verified-mode feed must supply work text
inline or through a same-host HTTPS `text/plain` link. Other works use theme-only
original generation and their source text is neither fetched nor sent.

- **PyonPyin Story Finder** runs weekly and can be run manually. It only discovers
  and records candidates.
- **PyonPyin Rights-Cleared Story Processing** runs weekly and can be run
  manually. It is inert until the explicit Gemini automation variable is true,
  then processes at most one queued draft per run. Source-based drafts require
  verified rights; unknown-rights drafts use only a broad theme. It cannot
  publish.
- **PyonPyin Backend Tests** run offline in CI. They do not need API keys and
  do not call Google services.
- **PyonPyin Tests and Optional Gemini Smoke Test** run offline tests on every
  workflow dispatch. The live smoke test runs only if `run_live_api_test` is
  explicitly checked; it makes one request, verifies HTTP success via the
  Gemini adapter, checks Myanmar Unicode and required draft sections, and does
  not print generated text or credentials.

GitHub scheduled jobs may be delayed or skipped by GitHub. Neither workflow
publishes stories.
The one-children/one-adult-per-week cadence remains an editorial target, not a
guarantee: rights review, audio readiness, and explicit human approval can
block or delay publication.

## Review and publication workflow

1. Discovery saves candidate metadata without inferring work-level copyright
   status. Unknown category stays `UNCLASSIFIED`.
2. With an explicit CHILDREN/ADULT category, unknown-rights works can be
   automatically queued for independent theme-only originals. Their rights
   fields remain uncleared; no discovered text/title/author is sent to Gemini.
3. Source-based retelling is available only under an explicitly verified
   source-level public-domain policy; the feed must provide text and the
   configured jurisdiction/evidence/reviewer/permissions must all be present.
4. Processing writes a Myanmar title/story, ordered episode data, quiz, and
   reflection to **Story Production** and **Story Episodes**, while retaining
   drafts for human review.
5. The reviewer edits the draft, verifies that all episode text still
   reconstructs the complete story, and completes content review. Audio is
   required by default; an authorized reviewer can explicitly change that
   choice to `NO` if the story will publish without narration.
6. Publication remains disabled until `PYONPYIN_PUBLISHING_ENABLED=true`.
   Publishing requires rights clearance for translation, AI processing, public
   distribution, a reviewed category, complete reviewed Myanmar text, complete
   ordered episodes, any required ready audio, a checked explicit approval
   control, and the approving person's name. Publication history is upserted
   by stable publication ID to avoid duplicates.

## Data fields and status semantics

- **Story Library:** stable ID, original title, author, source ID/name/URL,
  language/category/evidence, source license rule, work license URL/evidence,
  jurisdiction, explicit permission fields, review state, errors.
- **Story Production:** Myanmar full text/title, model and prompt version,
  episode references, quizzes/reflections, audio reference and requirement, processing,
  content review, rights-review, and publication-approval status.
- **Story Episodes:** stable story ID plus episode key, number, order, title,
  text, completeness and review state.
- **Processing History:** one row per explicit processing attempt with status,
  timestamps, model, retry count and safe error details.
- **Publishing History:** stable publication ID, story ID, public URL, timestamp,
  episode count, publication status, retries, errors, and approver.

Key states include `NEEDS_LICENSE_REVIEW`, `QUEUED`, `GENERATING`,
`DRAFT_READY`, `HUMAN_EDITING`, `APPROVED`, `PUBLISHED`, `BLOCKED_RIGHTS`,
`FAILED`, and `DISABLED`. Review dimensions are independent: content approval
does not imply rights clearance, and rights clearance does not imply publishing
approval.

## Testing and deployment

Run offline tests with `PYTHONPATH=src python -m unittest discover -s tests -v`.
The test suite exercises stable IDs, category caps, legacy-queue backfill,
rights gates, episode integrity, required audio checks, and both the
default-disabled publication route and explicit-approval requirement.
External Sheets, Gemini, TTS, and hosting integrations need separately
configured credentials and have not been exercised by offline tests. Long
texts use multiple bounded cells; generated episode text is capped at
40,000 characters per episode for Sheets compatibility.

For deployment, use a provider that supports Python 3.12 and environment
secrets, run behind HTTPS, and use a production WSGI server such as Gunicorn on
Linux (`gunicorn --chdir src pyonpyin.web_app:app`). Do not expose Flask's
development server to the internet. Public pages and private admin routes share
one application; protect admin routes at the app and hosting layers. No hosting
provider or paid service is selected by this repository.

## Cost and operational notes

- Google Sheets and Gemini may be usable within free quotas; Google can change
  availability, rate limits, and terms. Gemini requests may incur charges when
  a paid tier is selected or free quota is exhausted.
- GitHub Actions and web-host free tiers have limits and may sleep or throttle.
- TTS has not been activated. A paid account/service is not introduced or
  called by this project.
- Domain, hosting, audio storage, bandwidth, and human rights/language review
  can have costs. Check current provider pricing before deployment. The project
  makes no guarantee of zero-cost or 24/7 hosting.

No real stories have been published or public deployment performed.
