"""Run the SQLite queue beside the web server; external calls stay off HTTP requests."""

import argparse
import json
import os
import time
import uuid

from pyonpyin.config import load_environment
from pyonpyin.core import eligible_candidate, utc_now
from pyonpyin.storage import get_store
from pyonpyin.workflow import save_audio, story_snapshot


def run_once(store, client=None, tts=None):
    owner = uuid.uuid4().hex
    job = store.claim_job(owner)
    if job is None:
        return False
    try:
        report = {}
        # SQLite write transaction က worker နှစ်ခု တစ်ပုဒ်ကို ပြိုင်ရေးခြင်းနှင့် editorial edit ကို ကာကွယ်သည်။
        with store.transaction():
            kind, story_id = job["kind"], job["story_id"]
            if kind == "DISCOVER":
                import story_finder
                if story_finder.main(store, report=report) != 0:
                    raise RuntimeError("Discovery did not complete.")
            elif kind == "GENERATE":
                if os.environ.get("PYONPYIN_GEMINI_AUTOMATION_ENABLED", "").lower() != "true":
                    raise PermissionError("Gemini automation is disabled.")
                from process_stories import process_queued_stories
                _, production, _ = story_snapshot(store, story_id)
                if production.get("myanmar_story", "").strip():
                    raise ValueError("An existing draft cannot be overwritten by a generation retry.")
                if production.get("draft_mode") == "MANUAL_ORIGINAL":
                    raise ValueError("Manual originals cannot be sent to the generation queue.")
                production["processing_status"] = "QUEUED"
                store.write_production(production)
                if process_queued_stories(store, client=client, target_story_id=story_id):
                    raise RuntimeError("Generation failed; inspect processing history before retrying.")
            elif kind == "AUDIO":
                if os.environ.get("PYONPYIN_TTS_ENABLED", "").lower() != "true":
                    raise PermissionError("TTS is disabled.")
                from pyonpyin.audio import configured_provider
                library, production, _ = story_snapshot(store, story_id)
                if library.get("permission_for_audio") != "YES" or production.get("content_review_status") != "APPROVED":
                    raise PermissionError("Approved content and narration permission are required.")
                if production.get("draft_mode") not in {"ORIGINAL_THEME", "MANUAL_ORIGINAL"} and not eligible_candidate(library):
                    raise PermissionError("Source rights are no longer cleared.")
                provider = tts or configured_provider()
                if provider is None or not hasattr(provider, "synthesize_bytes"):
                    raise RuntimeError("Configure a supported speech provider (Gemini or Azure).")
                data = provider.synthesize_bytes(production["myanmar_story"])
                production.update(audio_url=save_audio(data, ".wav"), audio_status="PENDING_REVIEW", approval_status="")
                store.write_production(production)
            store.finish_job(job["job_id"], owner)
            store.record_processing({
                "processing_id": "job-" + job["job_id"], "story_id": story_id,
                "status": kind + "_SUCCEEDED", "started_at": job["updated_at"],
                "completed_at": utc_now(), "error_details": "",
                "result_json": json.dumps(report),
            })
    except Exception as exc:
        # Provider error text ထဲ key ပါနိုင်သဖြင့် exception အမျိုးအစားကိုသာ log/history တွင်သိမ်းသည်။
        store.finish_job(job["job_id"], owner, type(exc).__name__)
        store.record_processing({
            "processing_id": "job-" + job["job_id"], "story_id": job["story_id"],
            "status": job["kind"] + "_FAILED", "started_at": job["updated_at"],
            "completed_at": utc_now(), "error_details": type(exc).__name__,
            "result_json": json.dumps(report),
        })
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit")
    options = parser.parse_args()
    load_environment()
    store = get_store()
    if not hasattr(store, "claim_job"):
        raise SystemExit("Local worker requires PYONPYIN_STORAGE=sqlite.")
    try:
        while True:
            handled = run_once(store)
            if options.once:
                return
            if not handled:
                time.sleep(2)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
