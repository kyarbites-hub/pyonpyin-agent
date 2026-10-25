# MVP API contract

The current API is independent of the React layout. A replacement public website
and dashboard can use these endpoints. Use same-origin routing or an HTTPS reverse
proxy to the backend. Credentialed cross-origin CORS is not enabled. Keep provider
keys on the server. There is one shared editor identity in this MVP.

## Authentication and errors

`POST /api/admin/login` takes `{ "password": "..." }` and returns
`{ "csrf_token": "..." }`, setting an HttpOnly session cookie. Login attempts are
limited in SQLite mode. `GET /api/admin/overview` also returns the current CSRF token.
All admin mutations except login require `X-CSRF-Token` and the session cookie.
`POST /api/admin/logout` clears the session. Do not persist the token in a public URL.

API HTTP errors use `{ "error": "..." }`. Publication failures additionally return
`blockers: string[]`. Usual statuses are 400 invalid input/CSRF, 401 unauthenticated,
404 missing/private resource, 409 workflow conflict, 413 request too large, 429 login
limit, and 503 missing configuration or unavailable database. Successful job enqueue
returns HTTP 202; it does not mean the external API has succeeded.

## Public endpoints

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/stories` | Published and currently approved stories only |
| GET | `/api/stories/{id}` | One public story, or 404 |
| GET | `/media/audio/{server-generated-name}` | Range-capable audio; admins may preview drafts, others need a currently public READY asset |
| GET | `/health` | Process liveness |
| GET | `/ready` | Database readability; no provider request |

Public story fields: `story_id`, `category`, `title`, `story`, `episodes`, `audio_url`,
`quiz`, `reflection`. Episodes include their sequence, title, content, and reviewed
audio references when ready. Original provenance, private source text, and provider
credentials are not part of the public response. Audio uses private/no-store caching
so unpublishing also revokes subsequent audio requests. Previously downloaded bytes
cannot be recalled.

## Admin endpoints

| Method | Path | Purpose / body |
| --- | --- | --- |
| GET | `/api/admin/settings` | Non-secret configuration booleans, storage, voice; not live provider verification |
| GET | `/api/admin/audio` | Private listening catalogue: titles, real audio references, review state and latest audio job; no story/source text |
| GET | `/api/admin/overview` | Counts, review metadata, CSRF |
| GET | `/api/admin/jobs` | Existing processing/publishing history and GitHub dispatch capability |
| POST | `/api/admin/stories` | `{title, category: CHILDREN/ADULT, theme, story}`; optional empty `story` creates a theme draft workspace; returns 201 with `story_id` |
| GET | `/api/admin/story/{id}` | Private library/production metadata, reconstructed text, episodes, quiz, reflection |
| PUT | `/api/admin/story/{id}/draft` | `{myanmar_title, myanmar_story, episodes, quiz, reflection, audio_url, audio_status}` |
| PUT | `/api/admin/story/{id}/rights-review` | Existing source-rights review contract in `frontend/src/api.ts` |
| POST | `/api/admin/story/{id}/original-review` | `{reviewer, evidence, permission_for_publication: YES/NO, permission_for_audio: YES/NO}`; originals only |
| POST | `/api/admin/story/{id}/content-review` | `{action: approve/reject}`; never publishes |
| PUT | `/api/admin/story/{id}/audio-requirement` | `{required: boolean}`; invalidates publication approval |
| POST | `/api/admin/story/{id}/audio/upload` | Multipart `audio` file, MP3/PCM WAV, at most 25 MiB; stores PENDING_REVIEW |
| POST | `/api/admin/story/{id}/audio/review` | `{action: approve/reject, reviewer}`; listening review, READY only on approval |
| POST | `/api/admin/story/{id}/jobs` | `{kind: GENERATE/AUDIO}`; SQLite local queue; reuses an already active matching job |
| POST | `/api/admin/discovery` | `{}`; enqueue approved-feed discovery for the local worker |
| GET | `/api/admin/local-jobs` | Most recent 100 durable local jobs |
| POST | `/api/admin/local-jobs/{job_id}/retry` | `{confirm: true}`; failed/interrupted jobs only; policy rechecked by worker |
| POST | `/api/admin/story/{id}/publish` | `{confirm: true, approved_by}`; global switch plus all story gates required |
| POST | `/api/admin/story/{id}/unpublish` | `{approved_by}`; immediately revokes publication approval |

Original publication requires explicit provenance review, content review and
publication permission. Source-based adaptation still requires source rights,
translation and AI permissions. Narration permission is independent. Editing story
text clears original review, content approval, publication approval, and obsolete
audio. Quiz/episode edits require content review again. Saving an unchanged long
segmented story does not falsely invalidate audio due to an empty inline cell.

When a generated episode transcript differs from the complete generated story,
the generator reconstructs episodes from the full story without changing its text,
records `episode_partition_rebuilt=YES`, and leaves the result for human review.
Public and editor gates still require episodes to partition the full story.

The text editor omits audio fields on save. The server preserves the latest saved
audio reference, including a file generated after the editor was opened. Saving
unchanged text/episodes/quiz/reflection preserves content approval; genuine content
changes revoke it. PENDING_REVIEW/READY cannot be assigned without a saved audio URL.
The audio workspace shows the real player before listening approval, polls active
audio jobs to completion, and keeps optional uploads separate from AI generation.
The overview includes `has_story`, `audio_url`, and `updated_at` for mutually
exclusive dashboard stages: untouched, text draft, generated audio, and currently
published. Generated-but-unreviewed audio counts as generated, not audio approved.
`GET /api/admin/publications` lists publication events; the matching `/{id}`
returns an admin-only content snapshot when present. New SQLite publication
events retain the exact title, story, ordered episodes, category, and audio URL
even after draft edits. Older events without snapshots are labelled as such;
the archive separately shows the current public stories and audio.
Local discovery jobs include a persisted `result` with sources, errors, found,
duplicates, added, deferred, and queued counts. Repeated feed entries are skipped.
All-feed fetch failures fail the job rather than falsely reporting a successful
empty discovery. Discovery still does not grant rights or generate original stories.

Optional artwork:
- `POST /api/admin/story/{id}/cover-image`: multipart `image`; replaces the cover.
- `DELETE /api/admin/story/{id}/cover-image`: restores the default artwork.
- `POST` / `DELETE /api/admin/site/hero-image`: changes or removes homepage art.
- `GET /api/site`: exposes only `hero_image_url`.
- `GET /media/images/{uuid}.webp`: admin preview; public only for current hero or
  currently published story covers. Old images stay available to admins for archives.

Images are optional, never a publication gate. Changing images preserves content,
audio, and publication approval. JPG/PNG/WebP uploads are capped at 8 MiB and 20
million pixels, decoded and re-encoded without metadata, resized to at most 2400px,
and stored under `IMAGE_OUTPUT_DIR` (default `data/runtime/images`). Include this
folder alongside the database and audio directory in backups. New publication
snapshots also retain the cover URL. The dashboard editor manages story covers;
Settings manages the homepage “ပုံပြင်တစ်ပုဒ် · ကမ္ဘာတစ်ခု” artwork.
For original workspaces only, an AUDIO request may include
`confirm_original_narration: true` to record explicit admin narration consent in
the same transaction as enqueueing. Content approval is still required. This
does not approve provenance, grant publication permission, or publish anything;
source-based drafts still need their existing narration rights review. The audio
catalogue exposes `original_workspace` so the UI can show this consent beside
the generate button. Publication controls are collapsed separately.

Create-story starts with at most 40,000 characters; the draft editor supports up to
200,000 with at most 100 ordered episodes, each at most 40,000. Episode contents must
exactly reconstruct the story after whitespace normalization. Draft save requires at
least one quiz question/answer and a reflection. Azure narration is bounded to 20,000
characters and 25 MiB output; use reviewed uploaded audio for longer stories.

The default TTS provider is now `gemini`, sharing `GEMINI_API_KEY` with story
generation. `GEMINI_TTS_MODEL=gemini-3.8-flash-tts` and `GEMINI_TTS_VOICE=Kore`
configure the separate audio model and voice. The adapter uses the Interactions
REST API, requests stateless WAV output, and performs no automatic retries.
`PYONPYIN_TTS_ENABLED=true` is still required. Azure is an optional provider;
`GET /api/admin/settings` reports readiness for the selected provider only.

## Local queue and deployment boundary

Run `python -m pyonpyin.worker` beside the server, sharing the same persistent SQLite
database and audio folder. Jobs transition `QUEUED → RUNNING → SUCCEEDED/FAILED`.
Expired 15-minute leases become `INTERRUPTED` when a worker next checks the queue.
They are never automatically billed again. An administrator must inspect the
provider outcome before requesting retry. Existing generated editorial text is not
overwritten by a generation retry. The queue uses transactional claims and one
active job per story. Worker writes and admin mutations are transactional in SQLite.

The local MVP uses one persistent host/volume. It is not a distributed database or
an autoscaling multi-host design. SQLite mode disables GitHub dispatch because an
ephemeral Actions runner cannot access the host's local DB. The Sheets backend is
retained as an explicitly selected integration, without SQLite queue guarantees.
