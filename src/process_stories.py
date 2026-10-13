"""Create bounded, opt-in, rights-safe story drafts and save them to Sheets."""

import json
import os
import sys
import uuid

from pyonpyin.core import eligible_candidate, safe_story_theme, utc_now
from pyonpyin.gemini import GeminiClient
from pyonpyin.sheets import SheetsStore
from story_finder import queue_automatic_draft


PROMPT_VERSION = "myanmar-originality-v2"


def queue_eligible_stories(store, library_records, production_rows):
    """Queue safe library records once, using the discovery eligibility policy."""
    queued_count = 0
    for story in library_records:
        if queue_automatic_draft(store, story, production_rows):
            production_rows.append({
                "story_id": story["story_id"],
                "draft_mode": (
                    "PUBLIC_DOMAIN_RETELLING"
                    if story.get("rights_mode") == "VERIFIED_PUBLIC_DOMAIN"
                    else "ORIGINAL_THEME"
                ),
                "processing_status": "QUEUED",
                "content_review_status": "PENDING",
                "approval_status": "",
                "processing_error": "",
                "audio_required": "YES",
            })
            queued_count += 1
    return queued_count


def process_queued_stories(store, client=None, max_drafts=1):
    if max_drafts < 1:
        raise ValueError("max_drafts must be at least 1.")
    library_records = store.read_records("Story Library")
    library = {row.get("story_id"): row for row in library_records}
    production_rows = store.read_records("Story Production")
    queued_count = queue_eligible_stories(store, library_records, production_rows)
    if queued_count:
        print(f"Queued {queued_count} eligible Story Library record(s).")
    queued = [
        row for row in production_rows
        if row.get("processing_status", "").strip().upper() == "QUEUED"
    ][:max_drafts]
    if not queued:
        print("No selected stories are queued for processing.")
        return 0

    if any(
        row.get("draft_mode", "").strip().upper() != "ORIGINAL_THEME"
        for row in queued
    ):
        source_texts = store.read_texts("SOURCE")
    else:
        source_texts = {}

    failures = 0
    for production in queued:
        started_at = utc_now()
        story_id = production.get("story_id", "")
        processing_id = f"{story_id or 'missing'}-{uuid.uuid4().hex[:12]}"
        story = library.get(story_id)
        if story is None:
            failures += 1
            print(f"Cannot process {story_id or '(missing id)'}: library record is missing.")
            store.record_processing({
                "processing_id": processing_id,
                "story_id": story_id,
                "status": "FAILED",
                "started_at": started_at,
                "completed_at": utc_now(),
                "retry_count": "0",
                "error_details": "Library record is missing.",
            })
            continue
        mode = (
            production.get("draft_mode")
            or story.get("draft_mode")
            or (
                "ORIGINAL_THEME"
                if story.get("rights_mode") != "VERIFIED_PUBLIC_DOMAIN"
                and not story.get("license_status") == "APPROVED"
                else "RIGHTS_CLEARED_SOURCE"
            )
        ).strip().upper()
        story["draft_mode"] = mode

        if mode == "ORIGINAL_THEME":
            theme = safe_story_theme(
                story.get("category", ""), story.get("broad_theme", "")
            )
            source_text = ""
            if not theme:
                production.update({
                    "processing_status": "BLOCKED_POLICY",
                    "processing_error": "A reviewed story category is required for theme-only drafting.",
                })
                store.write_production(production)
                failures += 1
                store.record_processing({
                    "processing_id": processing_id,
                    "story_id": story_id,
                    "status": "BLOCKED_POLICY",
                    "started_at": started_at,
                    "completed_at": utc_now(),
                    "retry_count": "0",
                    "error_details": "A reviewed story category is required for theme-only drafting.",
                })
                continue
            story = {
                "story_id": story_id,
                "category": story["category"].strip().upper(),
                "draft_mode": "ORIGINAL_THEME",
                "broad_theme": theme,
            }
        else:
            story["source_text"] = (
                story.get("source_text", "") or source_texts.get(story_id, "")
            )
            if not eligible_candidate(story):
                production.update({
                    "processing_status": "BLOCKED_RIGHTS",
                    "processing_error": "Human rights clearance and evidence are required.",
                })
                store.write_production(production)
                failures += 1
                store.record_processing({
                    "processing_id": processing_id,
                    "story_id": story_id,
                    "status": "BLOCKED_RIGHTS",
                    "started_at": started_at,
                    "completed_at": utc_now(),
                    "retry_count": "0",
                    "error_details": "Rights clearance and evidence are required.",
                })
                continue
            source_text = story.get("source_text", "").strip()

        if mode != "ORIGINAL_THEME" and not source_text:
            production.update({
                "processing_status": "FAILED",
                "processing_error": "Rights-cleared source text is missing.",
            })
            store.write_production(production)
            failures += 1
            store.record_processing({
                "processing_id": processing_id,
                "story_id": story_id,
                "status": "FAILED",
                "started_at": started_at,
                "completed_at": utc_now(),
                "retry_count": "0",
                "error_details": "Rights-cleared source text is missing.",
            })
            continue

        production.update({
            "processing_status": "GENERATING",
            "processing_error": "",
            "draft_mode": mode,
            "license_review_status": (
                "NOT_USED_THEME_ONLY" if mode == "ORIGINAL_THEME" else "APPROVED"
            ),
        })
        store.write_production(production)
        retries_before = getattr(client, "retry_count", 0) if client is not None else 0
        try:
            if client is None:
                client = GeminiClient()
            draft = client.generate_draft(story, source_text)
            episodes = draft["episodes"]
            production.update({
                "myanmar_title": draft["title"],
                "myanmar_story": draft["story"],
                "episodes_json": json.dumps(episodes, ensure_ascii=False),
                "quiz_json": json.dumps(draft["quiz"], ensure_ascii=False),
                "reflection_json": json.dumps(draft["reflection"], ensure_ascii=False),
                "model_name": client.model,
                "prompt_version": PROMPT_VERSION,
                "content_review_status": "PENDING",
                "approval_status": "",
                "processing_status": "DRAFT_READY",
                "processing_error": "",
                "audio_status": "WAITING_PROVIDER_VERIFICATION",
                "updated_at": utc_now(),
            })
            store.write_production(production)
            store.write_episodes(story_id, episodes)
            store.record_processing({
                "processing_id": processing_id,
                "story_id": story_id,
                "status": "DRAFT_READY",
                "started_at": started_at,
                "completed_at": utc_now(),
                "model_name": client.model,
                "retry_count": str(getattr(client, "retry_count", retries_before) - retries_before),
                "error_details": "",
            })
            print(f"Draft ready for human review: {story_id}")
        except Exception as exc:
            production.update({
                "processing_status": "FAILED",
                "processing_error": type(exc).__name__,
            })
            store.write_production(production)
            store.record_processing({
                "processing_id": processing_id,
                "story_id": story_id,
                "status": "FAILED",
                "started_at": started_at,
                "completed_at": utc_now(),
                "model_name": getattr(client, "model", ""),
                "retry_count": str(getattr(client, "retry_count", 0) - retries_before),
                "error_details": type(exc).__name__,
            })
            print(f"Draft generation failed for {story_id}: {type(exc).__name__}")
            failures += 1
    return failures


def main():
    if os.environ.get("PYONPYIN_GEMINI_AUTOMATION_ENABLED", "").strip().lower() != "true":
        print("Gemini automation is disabled; set PYONPYIN_GEMINI_AUTOMATION_ENABLED=true to opt in.")
        return 0
    store = SheetsStore()
    store.ensure_schema()
    failures = process_queued_stories(store, max_drafts=1)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
