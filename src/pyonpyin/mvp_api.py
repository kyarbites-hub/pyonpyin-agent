"""UI-independent MVP endpoints, usable by the future public/admin websites."""

import json
import os
import re
import uuid
from contextlib import nullcontext
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, jsonify, request, send_from_directory, session

from pyonpyin.audio import MAX_AUDIO_BYTES, tts_configuration
from pyonpyin.core import eligible_candidate, publication_blockers, safe_story_theme, utc_now
from pyonpyin.storage import storage_backend
from pyonpyin.workflow import audio_directory, publicly_visible, save_audio, story_snapshot
from pyonpyin.images import image_directory, save_image


def register_mvp_api(app, store_factory, admin_required):
    blueprint = Blueprint("mvp", __name__)

    def mutation(function):
        @admin_required
        @wraps(function)
        def wrapped(*args, **kwargs):
            store = store_factory()
            try:
                with store.transaction() if hasattr(store, "transaction") else nullcontext():
                    return function(store, *args, **kwargs)
            except LookupError as exc:
                abort(404, str(exc))
            except ValueError as exc:
                abort(409, str(exc))
        return wrapped

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            abort(400, "A JSON object is required.")
        return value

    def text(value, field, limit=5_000):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            abort(400, f"{field} is required (maximum {limit} characters).")
        return value.strip()

    def idle(store, story_id):
        if hasattr(store, "has_active_job") and store.has_active_job(story_id):
            abort(409, "A job is active for this story. Wait or reconcile it first.")

    def local_queue(store):
        if not hasattr(store, "enqueue_job"):
            abort(409, "Local worker jobs require PYONPYIN_STORAGE=sqlite.")

    @blueprint.get("/api/site")
    def site_artwork():
        row = next((r for r in store_factory().read_records("Site Settings")
                    if r.get("setting_id") == "home_hero"), {})
        return jsonify({"hero_image_url": row.get("image_url", "")})

    @blueprint.post("/api/admin/site/hero-image")
    @mutation
    def upload_hero_image(store):
        upload = request.files.get("image")
        if upload is None:
            abort(400, "Choose an image file.")
        url = save_image(upload)
        store.upsert("Site Settings", "setting_id", {"setting_id": "home_hero", "image_url": url, "updated_at": utc_now()})
        return jsonify({"image_url": url})

    @blueprint.delete("/api/admin/site/hero-image")
    @mutation
    def remove_hero_image(store):
        store.upsert("Site Settings", "setting_id", {"setting_id": "home_hero", "image_url": "", "updated_at": utc_now()})
        return jsonify({"image_url": ""})

    @blueprint.route("/api/admin/story/<story_id>/cover-image", methods=["POST", "DELETE"])
    @mutation
    def story_cover_image(store, story_id):
        idle(store, story_id)
        _, production, _ = story_snapshot(store, story_id)
        url = ""
        if request.method == "POST":
            upload = request.files.get("image")
            if upload is None:
                abort(400, "Choose an image file.")
            url = save_image(upload)
        # ပုံထည့်/ပြောင်း/ဖယ်ခြင်းသည် ရွေးချယ်စရာဖြစ်ပြီး စာသား၊ အသံနှင့် ထုတ်ဝေမှုအတည်ပြုချက်ကို မပြောင်းပါ။
        production["cover_image_url"] = url
        store.write_production(production)
        return jsonify({"image_url": url})

    @blueprint.get("/media/images/<filename>")
    def image_asset(filename):
        if not re.fullmatch(r"[a-f0-9]{32}\.webp", filename):
            abort(404)
        store = store_factory()
        url = "/media/images/" + filename
        if not session.get("admin_authenticated"):
            hero = any(r.get("setting_id") == "home_hero" and r.get("image_url") == url
                       for r in store.read_records("Site Settings"))
            visible = hero
            if not visible:
                for production in store.read_records("Story Production"):
                    if production.get("cover_image_url") != url:
                        continue
                    library, draft, episodes = story_snapshot(store, production["story_id"])
                    if publicly_visible(store, library, draft, episodes):
                        visible = True
                        break
            if not visible:
                abort(404)
        response = send_from_directory(image_directory(), filename)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @blueprint.get("/api/admin/settings")
    @admin_required
    def settings():
        store = store_factory()
        return jsonify({
            "storage": storage_backend(), "local_jobs": hasattr(store, "enqueue_job"),
            "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
            "generation_enabled": os.environ.get("PYONPYIN_GEMINI_AUTOMATION_ENABLED", "").lower() == "true",
            "publishing_enabled": os.environ.get("PYONPYIN_PUBLISHING_ENABLED", "").lower() == "true",
            **tts_configuration(),
            "public_base_url_configured": bool(os.environ.get("PUBLIC_BASE_URL")),
        })

    @blueprint.post("/api/admin/stories")
    @mutation
    def create_story(store):
        data = body()
        title = text(data.get("title"), "title", 500)
        category = data.get("category")
        if category not in ("CHILDREN", "ADULT"):
            abort(400, "Choose CHILDREN or ADULT.")
        if not isinstance(data.get("theme", ""), str):
            abort(400, "theme must be text.")
        content = data.get("story", "")
        if not isinstance(content, str) or len(content) > 200_000:
            abort(400, "Story must be text of at most 200,000 characters.")
        if len(content) > 40_000:
            abort(400, "Use at most 40,000 characters initially; split longer text in the editor.")
        mode = "MANUAL_ORIGINAL" if content.strip() else "ORIGINAL_THEME"
        story_id = "pp-" + uuid.uuid4().hex[:24]
        store.upsert_story({
            "story_id": story_id, "original_title": title, "source_name": "Original workspace",
            "category": category, "category_evidence": "Explicit admin audience selection",
            "broad_theme": safe_story_theme(category, data.get("theme", "")),
            "rights_mode": "ORIGINAL", "rights_cleared": "NO", "license_status": "NOT_APPLICABLE",
            "permission_for_publication": "NO", "permission_for_audio": "NO",
            "original_review_status": "PENDING",
        })
        episodes = [{"episode_number": 1, "title": title, "content": content}] if content.strip() else []
        store.write_production({
            "story_id": story_id, "draft_mode": mode, "myanmar_title": title,
            "myanmar_story": content, "episodes_json": json.dumps(episodes, ensure_ascii=False),
            "quiz_json": "[]", "reflection_json": '""', "audio_required": "NO",
            "audio_status": "NOT_READY", "content_review_status": "PENDING", "approval_status": "",
            "processing_status": "HUMAN_EDITING" if content.strip() else "QUEUED",
        })
        store.write_episodes(story_id, episodes)
        return jsonify({"story_id": story_id, "draft_mode": mode}), 201

    @blueprint.get("/api/admin/audio")
    @admin_required
    def audio_library():
        store = store_factory()
        library = {row.get("story_id"): row for row in store.read_records("Story Library")}
        jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
        rows = []
        for production in store.read_records("Story Production"):
            story_id = production.get("story_id", "")
            story = library.get(story_id, {})
            url = production.get("audio_url", "")
            job = next((job for job in jobs if job["story_id"] == story_id and job["kind"] == "AUDIO"), None)
            rows.append({
                "story_id": story_id, "title": production.get("myanmar_title") or story.get("original_title", ""),
                "audio_url": url, "audio_status": production.get("audio_status", "NOT_READY") if url else "NOT_READY",
                "content_review_status": production.get("content_review_status", "PENDING"),
                "narration_permitted": story.get("permission_for_audio") == "YES",
                "original_workspace": production.get("draft_mode") in {"ORIGINAL_THEME", "MANUAL_ORIGINAL"},
                "updated_at": production.get("updated_at", ""),
                "job": {key: job.get(key, "") for key in ("job_id", "status", "error")} if job else None,
            })
        return jsonify(sorted(rows, key=lambda row: row["updated_at"], reverse=True))

    @blueprint.post("/api/admin/story/<story_id>/original-review")
    @mutation
    def review_original(store, story_id):
        idle(store, story_id)
        data = body()
        library, production, _ = story_snapshot(store, story_id)
        if production.get("draft_mode") not in {"ORIGINAL_THEME", "MANUAL_ORIGINAL"}:
            abort(409, "Use the source rights review for a source-based draft.")
        if not production.get("myanmar_story", "").strip():
            abort(409, "Create the story before reviewing original provenance.")
        if data.get("permission_for_publication") not in ("YES", "NO") or data.get("permission_for_audio") not in ("YES", "NO"):
            abort(400, "Publication and narration permissions must each be YES or NO.")
        library.update({
            "original_review_status": "APPROVED",
            "original_reviewer": text(data.get("reviewer"), "reviewer", 200),
            "original_evidence": text(data.get("evidence"), "original provenance evidence"),
            "permission_for_publication": data["permission_for_publication"],
            "permission_for_audio": data["permission_for_audio"],
        })
        production["approval_status"] = ""
        store.upsert_story(library)
        store.write_production(production)
        return jsonify({"ok": True})

    @blueprint.put("/api/admin/story/<story_id>/audio-requirement")
    @mutation
    def audio_requirement(store, story_id):
        idle(store, story_id)
        data = body()
        if type(data.get("required")) is not bool:
            abort(400, "required must be a boolean.")
        _, production, _ = story_snapshot(store, story_id)
        production.update(audio_required="YES" if data["required"] else "NO", approval_status="")
        store.write_production(production)
        return jsonify({"ok": True, "audio_required": production["audio_required"]})

    @blueprint.post("/api/admin/story/<story_id>/publish")
    @mutation
    def publish(store, story_id):
        idle(store, story_id)
        data = body()
        if data.get("confirm") is not True:
            abort(400, "Explicit confirm=true is required.")
        reviewer = text(data.get("approved_by"), "approving reviewer", 200)
        if os.environ.get("PYONPYIN_PUBLISHING_ENABLED", "").lower() != "true":
            abort(503, "Publishing is disabled. Enable it explicitly in server settings.")
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        url = urlsplit(base)
        if (not url.hostname or url.username or url.password or url.query or url.fragment
                or url.path not in {"", "/"} or url.scheme not in {"https", "http"}
                or url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1"}):
            abort(503, "Configure PUBLIC_BASE_URL as HTTPS (localhost HTTP is allowed).")
        library, production, episodes = story_snapshot(store, story_id)
        production["approval_status"] = "APPROVED"
        blockers = publication_blockers({**library, **production}, episodes,
                                        production.get("audio_required") == "YES")
        if blockers:
            return jsonify({"error": "Publication blocked.", "blockers": blockers}), 409
        store.write_production(production)
        store.record_publication({
            "publication_id": uuid.uuid4().hex, "story_id": story_id,
            "publication_status": "PUBLISHED", "published_title": production["myanmar_title"],
            "website_url": f"{base}/app/#/stories/{story_id}", "published_at": utc_now(),
            "episode_count": str(len(episodes)), "approved_by": reviewer,
            "audio_url": production.get("audio_url", ""),
            # ထုတ်ဝေပြီးနောက် မူကြမ်းပြင်လည်း ထိုအချိန်က စာသားနှင့် အသံဖိုင်မှတ်တမ်း မပျောက်စေရန် သိမ်းသည်။
            "snapshot_json": json.dumps({
                "title": production["myanmar_title"], "story": production["myanmar_story"],
                "episodes": episodes, "audio_url": production.get("audio_url", ""),
                "category": library.get("category", ""),
                "cover_image_url": production.get("cover_image_url", ""),
            }, ensure_ascii=False),
        })
        return jsonify({"ok": True, "story_id": story_id})

    @blueprint.get("/api/admin/publications")
    @admin_required
    def publications():
        # မှတ်တမ်းစာရင်းတွင် စာသားအပြည့်ကို မပို့ဘဲ အသေးစိတ်ဖွင့်မှသာ snapshot ကိုဖတ်ပေးသည်။
        rows = store_factory().read_records("Publishing History")
        keys = ("publication_id", "story_id", "published_title", "website_url", "published_at",
                "publication_status", "approved_by", "audio_url")
        return jsonify([{**{key: row.get(key, "") for key in keys},
                         "snapshot_available": bool(row.get("snapshot_json"))}
                        for row in sorted(rows, key=lambda row: row.get("published_at", ""), reverse=True)])

    @blueprint.get("/api/admin/publications/<publication_id>")
    @admin_required
    def publication_snapshot(publication_id):
        row = next((r for r in store_factory().read_records("Publishing History")
                    if r.get("publication_id") == publication_id), None)
        if row is None:
            abort(404)
        if not row.get("snapshot_json"):
            abort(404, "This older event has no saved content snapshot.")
        return jsonify(json.loads(row["snapshot_json"]))

    @blueprint.post("/api/admin/story/<story_id>/unpublish")
    @mutation
    def unpublish(store, story_id):
        idle(store, story_id)
        reviewer = text(body().get("approved_by"), "reviewer", 200)
        _, production, _ = story_snapshot(store, story_id)
        production["approval_status"] = ""
        store.write_production(production)
        store.record_publication({"publication_id": uuid.uuid4().hex, "story_id": story_id,
                                  "publication_status": "UNPUBLISHED", "published_at": utc_now(),
                                  "approved_by": reviewer})
        return jsonify({"ok": True})

    @blueprint.post("/api/admin/story/<story_id>/audio/upload")
    @mutation
    def upload_audio(store, story_id):
        idle(store, story_id)
        library, production, _ = story_snapshot(store, story_id)
        if library.get("permission_for_audio") != "YES" or not production.get("myanmar_story", "").strip():
            abort(409, "Narration permission and a complete story are required.")
        upload = request.files.get("audio")
        if upload is None:
            abort(400, "Upload a file in the audio field.")
        suffix = Path(upload.filename or "").suffix.lower()
        url = save_audio(upload.stream.read(MAX_AUDIO_BYTES + 1), suffix)
        production.update(audio_url=url, audio_status="PENDING_REVIEW", approval_status="")
        store.write_production(production)
        return jsonify({"ok": True, "audio_url": url, "audio_status": "PENDING_REVIEW"})

    @blueprint.post("/api/admin/story/<story_id>/audio/review")
    @mutation
    def review_audio(store, story_id):
        idle(store, story_id)
        data = body()
        reviewer = text(data.get("reviewer"), "reviewer", 200)
        library, production, _ = story_snapshot(store, story_id)
        if data.get("action") not in ("approve", "reject"):
            abort(400, "Choose approve or reject.")
        if library.get("permission_for_audio") != "YES" or not production.get("audio_url"):
            abort(409, "Audio permission and a saved audio asset are required.")
        production.update(audio_status="READY" if data["action"] == "approve" else "NOT_READY", approval_status="")
        store.write_production(production)
        store.record_processing({"processing_id": uuid.uuid4().hex, "story_id": story_id,
                                 "status": "AUDIO_" + data["action"].upper(), "completed_at": utc_now(),
                                 "error_details": "", "reviewer": reviewer})
        return jsonify({"ok": True, "audio_status": production["audio_status"]})

    @blueprint.get("/media/audio/<filename>")
    def audio_asset(filename):
        if not re.fullmatch(r"[a-f0-9]{32}\.(wav|mp3)", filename):
            abort(404)
        if not session.get("admin_authenticated"):
            store = store_factory()
            allowed = False
            for draft in store.read_records("Story Production"):
                if draft.get("audio_url") != "/media/audio/" + filename or draft.get("audio_status") != "READY":
                    continue
                try:
                    library, production, episodes = story_snapshot(store, draft["story_id"])
                    allowed = publicly_visible(store, library, production, episodes)
                except (LookupError, ValueError):
                    pass
                if allowed:
                    break
            if not allowed:
                abort(404)
        response = send_from_directory(audio_directory(), filename, conditional=True)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @blueprint.get("/api/admin/local-jobs")
    @admin_required
    def jobs():
        store = store_factory()
        local_queue(store)
        reports = {row.get("processing_id"): row.get("result_json", "")
                   for row in store.read_records("Processing History")}
        return jsonify([{**job, "result": json.loads(reports.get("job-" + job["job_id"]) or "null")}
                        for job in store.list_jobs()])

    @blueprint.post("/api/admin/story/<story_id>/jobs")
    @mutation
    def enqueue(store, story_id):
        local_queue(store)
        data = body()
        kind = data.get("kind")
        library, production, _ = story_snapshot(store, story_id)
        if kind == "GENERATE":
            if os.environ.get("PYONPYIN_GEMINI_AUTOMATION_ENABLED", "").lower() != "true" or not os.environ.get("GEMINI_API_KEY"):
                abort(503, "Configure GEMINI_API_KEY and enable Gemini automation.")
            if production.get("myanmar_story", "").strip():
                abort(409, "A draft already exists. Create a new story to avoid overwriting editorial work.")
            if production.get("draft_mode") == "ORIGINAL_THEME":
                if not safe_story_theme(library.get("category"), library.get("broad_theme")):
                    abort(409, "A reviewed audience category is required.")
            elif not eligible_candidate(library):
                abort(409, "Source rights must be cleared before generation.")
        elif kind == "AUDIO":
            configuration = tts_configuration()
            if not configuration["tts_enabled"] or not configuration["tts_configured"]:
                abort(503, "Configure the selected speech provider and explicitly enable TTS.")
            # ကိုယ်ပိုင်ပုံပြင်ကို အသံထုတ်ခွင့်ပေးခြင်းသည် မူရင်းနှင့် ထုတ်ဝေခွင့် စစ်ဆေးအတည်ပြုခြင်း မဟုတ်ပါ။
            consent = (data.get("confirm_original_narration") is True
                       and production.get("draft_mode") in {"ORIGINAL_THEME", "MANUAL_ORIGINAL"})
            if (library.get("permission_for_audio") != "YES" and not consent) or production.get("content_review_status") != "APPROVED":
                abort(409, "Approve story content and narration permission before synthesis.")
            if not 0 < len(production.get("myanmar_story", "")) <= 20_000:
                abort(409, "Automatic narration supports 1–20,000 characters.")
            if consent and library.get("permission_for_audio") != "YES":
                library.update(permission_for_audio="YES", narration_consent_at=utc_now(),
                               narration_consent_actor="authenticated admin")
                store.upsert_story(library)
        else:
            abort(400, "Choose GENERATE or AUDIO.")
        job = store.enqueue_job(story_id, kind)
        if kind == "GENERATE":
            production["processing_status"] = "QUEUED"
            store.write_production(production)
        return jsonify(job), 202

    @blueprint.post("/api/admin/discovery")
    @mutation
    def discovery(store):
        local_queue(store)
        return jsonify(store.enqueue_job("discovery", "DISCOVER")), 202

    @blueprint.post("/api/admin/local-jobs/<job_id>/retry")
    @mutation
    def retry_job(store, job_id):
        local_queue(store)
        if body().get("confirm") is not True:
            abort(400, "Explicit retry confirmation is required.")
        old = next((j for j in store.list_jobs() if j["job_id"] == job_id), None)
        if not old:
            abort(404)
        if old["status"] not in {"FAILED", "INTERRUPTED"}:
            abort(409, "Only failed or interrupted jobs can be retried.")
        # Worker က policy ကို ပြန်စစ်သည်။ ရလဒ်ရှိပြီးသား generation ကို ထပ်မရေးပါ။
        return jsonify(store.enqueue_job(old["story_id"], old["kind"])), 202

    app.register_blueprint(blueprint)
