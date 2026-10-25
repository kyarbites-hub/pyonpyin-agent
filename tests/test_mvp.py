"""Real temporary SQLite end-to-end workflows; no billable requests."""

import io
import json
import os
import tempfile
import unittest
import wave
import base64
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from pyonpyin import web_app
from pyonpyin.audio import AzureSpeechTTS, AudioUnavailable, GeminiSpeechTTS, configured_provider
from pyonpyin.sqlite_store import SQLiteStore
from pyonpyin.worker import run_once


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0\0" * 2400)
    return buffer.getvalue()


class MVPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.environment = patch.dict(os.environ, {
            "PYONPYIN_STORAGE": "sqlite", "PYONPYIN_DATABASE_PATH": str(self.path / "app.db"),
            "PYONPYIN_ENV_FILE": str(self.path / "no-local-env"),
            "AUDIO_OUTPUT_DIR": str(self.path / "audio"), "PYONPYIN_PUBLISHING_ENABLED": "true",
            "IMAGE_OUTPUT_DIR": str(self.path / "images"),
            "PUBLIC_BASE_URL": "http://127.0.0.1:8000", "PYONPYIN_ADMIN_PASSWORD": "test-password",
            "PYONPYIN_SESSION_SECRET": "test-secret", "PYONPYIN_GEMINI_AUTOMATION_ENABLED": "false",
            "PYONPYIN_TTS_ENABLED": "false", "GEMINI_API_KEY": "", "AZURE_SPEECH_KEY": "",
            "GEMINI_TTS_MODEL": "gemini-3.8-flash-tts", "GEMINI_TTS_VOICE": "Kore",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.store = SQLiteStore()
        self.client = web_app.app.test_client()
        self.public = web_app.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_authenticated"] = True
            session["csrf_token"] = "test-csrf"
        self.headers = {"X-CSRF-Token": "test-csrf"}

    def post(self, path, data=None):
        return self.client.post(path, json=data or {}, headers=self.headers)

    def create(self, content="ပုံပြင်စာသား"):
        response = self.post("/api/admin/stories", {
            "title": "ကိုယ်ပိုင်ပုံပြင်", "category": "CHILDREN", "theme": "kindness", "story": content,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["story_id"]

    def save_draft(self, story_id, content="ပုံပြင်စာသား"):
        return self.client.put(f"/api/admin/story/{story_id}/draft", json={
            "myanmar_title": "ကိုယ်ပိုင်ပုံပြင်", "myanmar_story": content,
            "episodes": [{"episode_number": 1, "title": "ပထမပိုင်း", "content": content}],
            "quiz": [{"question": "ဘာသင်ယူရသလဲ", "answer": "ကြင်နာမှု"}],
            "reflection": "ဒီနေ့ဘယ်လိုကူညီမလဲ", "audio_url": "", "audio_status": "NOT_READY",
        }, headers=self.headers)

    def review(self, story_id):
        response = self.post(f"/api/admin/story/{story_id}/original-review", {
            "reviewer": "Editor", "evidence": "Independently written and reviewed original.",
            "permission_for_publication": "YES", "permission_for_audio": "YES",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        response = self.post(f"/api/admin/story/{story_id}/content-review", {"action": "approve"})
        self.assertEqual(response.status_code, 200, response.get_json())

    def publish(self, story_id):
        return self.post(f"/api/admin/story/{story_id}/publish", {"confirm": True, "approved_by": "Editor"})

    def test_manual_original_full_lifecycle_and_private_learning_data(self):
        story_id = self.create()
        self.assertEqual(self.public.get("/api/stories").get_json(), [])
        self.assertEqual(self.save_draft(story_id).status_code, 200)
        blocked = self.publish(story_id)
        self.assertEqual(blocked.status_code, 409)
        self.assertTrue(blocked.get_json()["blockers"])
        self.review(story_id)
        self.assertEqual(self.public.get("/api/stories").get_json(), [])
        self.assertEqual(self.publish(story_id).status_code, 200)
        published = self.public.get(f"/api/stories/{story_id}")
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.get_json()["quiz"][0]["answer"], "ကြင်နာမှု")
        self.assertEqual(published.get_json()["reflection"], "ဒီနေ့ဘယ်လိုကူညီမလဲ")
        self.assertNotIn("original_evidence", published.get_json())
        self.assertEqual(self.post(f"/api/admin/story/{story_id}/unpublish", {"approved_by": "Editor"}).status_code, 200)
        self.assertEqual(self.public.get(f"/api/stories/{story_id}").status_code, 404)

    def test_mutations_require_authentication_and_csrf_and_never_leak_keys(self):
        self.assertEqual(self.public.get("/api/admin/settings").status_code, 401)
        self.assertEqual(self.public.post("/api/admin/stories", json={}).status_code, 400)
        self.assertEqual(self.client.post("/api/admin/stories", json={}).status_code, 400)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "very-private-key", "AZURE_SPEECH_KEY": "another-private-key"}):
            settings = self.client.get("/api/admin/settings")
            self.assertNotIn(b"very-private-key", settings.data)
            self.assertNotIn(b"another-private-key", settings.data)

    def test_audio_requires_listening_review_and_is_private_until_publication(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        upload = self.client.post(f"/api/admin/story/{story_id}/audio/upload", data={
            "audio": (io.BytesIO(wav_bytes()), "story.wav")}, headers=self.headers)
        self.assertEqual(upload.status_code, 200, upload.get_json())
        url = upload.get_json()["audio_url"]
        self.assertEqual(self.public.get(url).status_code, 404)
        with self.client.get(url) as preview:
            self.assertEqual(preview.status_code, 200)
        self.assertEqual(self.client.put(f"/api/admin/story/{story_id}/audio-requirement", json={"required": True}, headers=self.headers).status_code, 200)
        self.assertEqual(self.publish(story_id).status_code, 409)
        self.assertEqual(self.post(f"/api/admin/story/{story_id}/audio/review", {"action": "approve", "reviewer": "Listener"}).status_code, 200)
        self.assertEqual(self.publish(story_id).status_code, 200)
        response = self.public.get(url, headers={"Range": "bytes=0-20"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        response.close()
        self.post(f"/api/admin/story/{story_id}/unpublish", {"approved_by": "Editor"})
        self.assertEqual(self.public.get(url).status_code, 404)

    def test_invalid_upload_and_invalid_draft_do_not_change_saved_story(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        response = self.client.post(f"/api/admin/story/{story_id}/audio/upload", data={
            "audio": (io.BytesIO(b"<script>not audio</script>"), "fake.wav")}, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertFalse((self.path / "audio").exists())
        original = self.client.get(f"/api/admin/story/{story_id}").get_json()
        response = self.client.put(f"/api/admin/story/{story_id}/draft", json={
            "myanmar_title": "Changed", "myanmar_story": "different", "episodes": [],
        }, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f"/api/admin/story/{story_id}").get_json(), original)

    def test_audio_library_is_private_and_does_not_claim_an_empty_reference_is_ready(self):
        story_id = self.create()
        self.store.write_production({"story_id": story_id, "audio_url": "", "audio_status": "PENDING_REVIEW"})
        self.assertEqual(self.public.get("/api/admin/audio").status_code, 401)
        rows = self.client.get("/api/admin/audio").get_json()
        self.assertEqual(rows[0]["audio_url"], "")
        self.assertEqual(rows[0]["audio_status"], "NOT_READY")
        self.assertNotIn("myanmar_story", rows[0])

    def test_unchanged_text_save_preserves_content_approval_and_audio_without_client_audio_fields(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        upload = self.client.post(f"/api/admin/story/{story_id}/audio/upload", data={
            "audio": (io.BytesIO(wav_bytes()), "story.wav")}, headers=self.headers)
        self.assertEqual(upload.status_code, 200)
        self.post(f"/api/admin/story/{story_id}/audio/review", {"action": "approve", "reviewer": "Listener"})
        self.assertEqual(self.publish(story_id).status_code, 200)
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        response = self.client.put(f"/api/admin/story/{story_id}/draft", json={
            "myanmar_title": detail["production"]["myanmar_title"],
            "myanmar_story": detail["production"]["myanmar_story"],
            "episodes": detail["episodes"], "quiz": detail["quiz"], "reflection": detail["reflection"],
        }, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(response.get_json()["content_changed"])
        updated = self.client.get(f"/api/admin/story/{story_id}").get_json()["production"]
        self.assertEqual(updated["content_review_status"], "APPROVED")
        self.assertEqual(updated["audio_status"], "READY")
        self.assertEqual(updated["audio_url"], upload.get_json()["audio_url"])
        self.assertEqual(updated["approval_status"], "APPROVED")
        rows = self.client.get("/api/admin/audio").get_json()
        self.assertEqual(rows[0]["audio_url"], updated["audio_url"])

    def test_pending_audio_review_cannot_be_saved_without_an_audio_asset(self):
        story_id = self.create()
        self.save_draft(story_id)
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        response = self.client.put(f"/api/admin/story/{story_id}/draft", json={
            "myanmar_title": detail["production"]["myanmar_title"],
            "myanmar_story": detail["production"]["myanmar_story"],
            "episodes": detail["episodes"], "quiz": detail["quiz"], "reflection": detail["reflection"],
            "audio_url": "", "audio_status": "PENDING_REVIEW",
        }, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_editing_published_text_revokes_original_and_publication_approval(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        self.publish(story_id)
        self.assertEqual(self.save_draft(story_id, "ပြင်ဆင်ထားသောစာသား").status_code, 200)
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        self.assertEqual(detail["story"]["original_review_status"], "PENDING")
        self.assertEqual(detail["production"]["approval_status"], "")
        self.assertEqual(self.public.get(f"/api/stories/{story_id}").status_code, 404)

    def test_generation_is_opt_in_queue_is_durable_and_worker_preserves_draft(self):
        story_id = self.create("")
        path = f"/api/admin/story/{story_id}/jobs"
        self.assertEqual(self.post(path, {"kind": "GENERATE"}).status_code, 503)
        class FakeGemini:
            model = "offline-model"
            retry_count = 0
            def generate_draft(self, story, source):
                self.source = source
                return {"title": "AI ပုံပြင်", "story": "မူကြမ်း", "episodes": [
                    {"episode_number": 1, "title": "အစ", "content": "မူကြမ်း"}],
                    "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}], "reflection": "စဉ်းစားရန်"}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-not-live", "PYONPYIN_GEMINI_AUTOMATION_ENABLED": "true"}):
            first = self.post(path, {"kind": "GENERATE"})
            second = self.post(path, {"kind": "GENERATE"})
            self.assertEqual(first.status_code, 202)
            self.assertEqual(first.get_json()["job_id"], second.get_json()["job_id"])
            self.assertEqual(self.save_draft(story_id).status_code, 409)
            client = FakeGemini()
            self.assertTrue(run_once(SQLiteStore(), client=client))
            self.assertEqual(client.source, "")
            self.assertEqual(SQLiteStore().list_jobs()[0]["status"], "SUCCEEDED")
            detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
            self.assertEqual(detail["production"]["content_review_status"], "PENDING")
            self.assertEqual(detail["production"]["myanmar_story"], "မူကြမ်း")
            self.assertEqual(self.post(path, {"kind": "GENERATE"}).status_code, 409)

    def test_original_narration_consent_does_not_approve_provenance_or_publication(self):
        story_id = self.create()
        self.save_draft(story_id)
        path = f"/api/admin/story/{story_id}/jobs"
        with patch.dict(os.environ, {"TTS_PROVIDER": "gemini", "PYONPYIN_TTS_ENABLED": "true", "GEMINI_API_KEY": "offline-key"}):
            self.assertEqual(self.post(path, {"kind": "AUDIO", "confirm_original_narration": True}).status_code, 409)
            self.post(f"/api/admin/story/{story_id}/content-review", {"action": "approve"})
            self.assertEqual(self.post(path, {"kind": "AUDIO"}).status_code, 409)
            self.assertEqual(self.post(path, {"kind": "AUDIO", "confirm_original_narration": True}).status_code, 202)
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        self.assertEqual(detail["story"]["permission_for_audio"], "YES")
        self.assertEqual(detail["story"]["permission_for_publication"], "NO")
        self.assertEqual(detail["story"]["original_review_status"], "PENDING")
        self.assertFalse(detail["production"].get("approval_status"))

    def test_narration_consent_cannot_grant_source_rights(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.post(f"/api/admin/story/{story_id}/content-review", {"action": "approve"})
        self.store.write_production({"story_id": story_id, "draft_mode": "SOURCE_BASED"})
        with patch.dict(os.environ, {"TTS_PROVIDER": "gemini", "PYONPYIN_TTS_ENABLED": "true", "GEMINI_API_KEY": "offline-key"}):
            response = self.post(f"/api/admin/story/{story_id}/jobs", {"kind": "AUDIO", "confirm_original_narration": True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.read_records("Story Library")[0]["permission_for_audio"], "NO")

    def test_worker_audio_never_approves_its_own_output(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        class FakeTTS:
            def synthesize_bytes(self, text):
                return wav_bytes()
        with patch.dict(os.environ, {"TTS_PROVIDER": "azure", "PYONPYIN_TTS_ENABLED": "true", "AZURE_SPEECH_KEY": "offline-key", "AZURE_SPEECH_REGION": "eastus"}):
            result = self.post(f"/api/admin/story/{story_id}/jobs", {"kind": "AUDIO"})
            self.assertEqual(result.status_code, 202)
            run_once(SQLiteStore(), tts=FakeTTS())
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        self.assertEqual(detail["production"]["audio_status"], "PENDING_REVIEW")
        self.assertEqual(self.public.get(detail["production"]["audio_url"]).status_code, 404)

    def test_optional_cover_can_be_added_replaced_and_removed_after_publication(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        self.assertEqual(self.publish(story_id).status_code, 200)
        def upload(color):
            data = io.BytesIO()
            Image.new("RGB", (32, 24), color).save(data, format="PNG")
            data.seek(0)
            return self.client.post(f"/api/admin/story/{story_id}/cover-image", data={"image": (data, "cover.png")}, headers=self.headers)
        first = upload("red")
        self.assertEqual(first.status_code, 200)
        old_url = first.get_json()["image_url"]
        second = upload("blue")
        url = second.get_json()["image_url"]
        self.assertNotEqual(url, old_url)
        public = self.public.get(f"/api/stories/{story_id}")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.get_json()["cover_image_url"], url)
        with self.public.get(url) as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.public.get(old_url).status_code, 404)
        with self.client.get(old_url) as response:
            self.assertEqual(response.status_code, 200)
        response = self.client.delete(f"/api/admin/story/{story_id}/cover-image", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.public.get(f"/api/stories/{story_id}").get_json()["cover_image_url"], "")
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        self.assertEqual(detail["production"]["content_review_status"], "APPROVED")
        self.assertEqual(detail["production"]["approval_status"], "APPROVED")

    def test_private_cover_validation_and_public_home_image(self):
        story_id = self.create()
        path = f"/api/admin/story/{story_id}/cover-image"
        self.assertEqual(self.public.post(path).status_code, 400)
        with self.public.session_transaction() as session:
            session["csrf_token"] = "public-csrf"
        self.assertEqual(self.public.post(path, headers={"X-CSRF-Token": "public-csrf"}).status_code, 401)
        self.assertEqual(self.client.post(path, data={"image": (io.BytesIO(b'<svg/>'), "fake.png")}, headers=self.headers).status_code, 409)
        self.assertEqual(list((self.path / "images").glob("*")), [])
        def image():
            data = io.BytesIO()
            Image.new("RGB", (32, 24), "red").save(data, format="PNG")
            data.seek(0)
            return {"image": (data, "../cover.png")}
        url = self.client.post(path, data=image(), headers=self.headers).get_json()["image_url"]
        self.assertEqual(self.public.get(url).status_code, 404)
        with self.client.get(url) as response:
            self.assertEqual(response.status_code, 200)
        hero = self.client.post("/api/admin/site/hero-image", data=image(), headers=self.headers).get_json()["image_url"]
        self.assertEqual(self.public.get("/api/site").get_json()["hero_image_url"], hero)
        with self.public.get(hero) as response:
            self.assertEqual(response.status_code, 200)
        self.client.delete("/api/admin/site/hero-image", headers=self.headers)
        self.assertEqual(self.public.get("/api/site").get_json()["hero_image_url"], "")
        self.assertEqual(self.public.get(hero).status_code, 404)

    def test_publication_snapshot_survives_edits_and_stays_admin_only(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        self.assertEqual(self.publish(story_id).status_code, 200)
        row = self.client.get("/api/admin/publications").get_json()[0]
        self.assertTrue(row["snapshot_available"])
        path = "/api/admin/publications/" + row["publication_id"]
        self.assertEqual(self.public.get(path).status_code, 401)
        before = self.client.get(path).get_json()
        self.save_draft(story_id, "ပြင်ဆင်ထားသောစာသား")
        self.assertEqual(self.client.get(path).get_json(), before)
        self.assertEqual(before["story"], "ပုံပြင်စာသား")

    def test_discovery_result_distinguishes_duplicates_and_feed_failure(self):
        sources = [{"source_name": "Fixture", "approval_status": "APPROVED", "automation_allowed": True,
                    "feed_url": "https://example.org/feed"}]
        books = [{"title": "Feed book", "source_id": "feed-book", "source_url": "https://example.org/book"}]
        with patch("story_finder.load_approved_sources", return_value=sources), patch("story_finder.fetch_new_books", side_effect=lambda *args, **kwargs: [dict(b) for b in books]):
            for _ in range(2):
                self.store.enqueue_job("discovery", "DISCOVER")
                self.assertTrue(run_once(self.store))
        job = self.client.get("/api/admin/local-jobs").get_json()[0]
        self.assertEqual(job["status"], "SUCCEEDED")
        self.assertEqual(job["result"]["added"], 0)
        self.assertEqual(job["result"]["duplicates"], 1)
        def unavailable(*args, **kwargs):
            kwargs["diagnostics"].append("HTTP 503")
            return []
        with patch("story_finder.load_approved_sources", return_value=sources), patch("story_finder.fetch_new_books", side_effect=unavailable):
            self.store.enqueue_job("discovery", "DISCOVER")
            run_once(self.store)
        job = self.client.get("/api/admin/local-jobs").get_json()[0]
        self.assertEqual(job["status"], "FAILED")
        self.assertEqual(job["result"]["sources"][0]["errors"], ["HTTP 503"])

    def test_failed_generation_is_not_automatically_billed_again(self):
        story_id = self.create("")
        class FailingGemini:
            model = "offline-model"
            retry_count = 0
            calls = 0
            def generate_draft(self, story, source):
                self.calls += 1
                raise RuntimeError("private provider detail must not be logged")
        provider = FailingGemini()
        with patch.dict(os.environ, {"PYONPYIN_GEMINI_AUTOMATION_ENABLED": "true", "GEMINI_API_KEY": "offline-key"}):
            self.post(f"/api/admin/story/{story_id}/jobs", {"kind": "GENERATE"})
            self.assertTrue(run_once(self.store, client=provider))
            self.assertFalse(run_once(self.store, client=provider))
        self.assertEqual(provider.calls, 1)
        job = self.store.list_jobs()[0]
        self.assertEqual(job["status"], "FAILED")
        self.assertNotIn("private provider", json.dumps(self.store.read_records("Processing History")))
        self.assertEqual(self.public.get("/api/stories").get_json(), [])

    def test_discovery_worker_persists_to_sqlite_without_accessing_legacy_google_queue(self):
        self.store.enqueue_job("discovery", "DISCOVER")
        sources = [{"source_name": "Approved fixture", "approval_status": "APPROVED",
                    "automation_allowed": True, "feed_url": "https://example.org/feed"}]
        books = [{"title": "Feed book", "source_id": "feed-book", "source_url": "https://example.org/book",
                  "source_category_raw": "CHILDREN"}]
        with patch("story_finder.load_approved_sources", return_value=sources), patch(
            "story_finder.fetch_new_books", return_value=books
        ), patch("story_finder.existing_source_queue_urls") as legacy:
            self.assertTrue(run_once(self.store))
        legacy.assert_not_called()
        self.assertEqual(self.store.list_jobs()[0]["status"], "SUCCEEDED")
        self.assertEqual(self.store.read_records("Story Library")[0]["category"], "CHILDREN")
        self.assertEqual(self.store.read_records("Story Production")[0]["processing_status"], "QUEUED")

    def test_worker_claim_is_atomic_across_connections_and_expired_job_needs_retry(self):
        job = self.store.enqueue_job("one-story", "GENERATE")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda owner: SQLiteStore().claim_job(owner), ["worker-a", "worker-b"]))
        self.assertEqual(sum(r is not None for r in results), 1)
        with self.store.connection() as connection:
            connection.execute("UPDATE jobs SET lease_until=0 WHERE job_id=?", (job["job_id"],))
        self.assertIsNone(self.store.claim_job("new-worker"))
        self.assertEqual(self.store.list_jobs()[0]["status"], "INTERRUPTED")
        retried = self.post(f"/api/admin/local-jobs/{job['job_id']}/retry", {"confirm": True})
        self.assertEqual(retried.status_code, 202)
        self.assertNotEqual(retried.get_json()["job_id"], job["job_id"])

    def test_database_backup_restores_records_and_transaction_rolls_back(self):
        story_id = self.create()
        with self.assertRaises(ValueError):
            with self.store.transaction():
                self.store.upsert_story({"story_id": story_id, "original_title": "Should rollback"})
                raise ValueError("test")
        self.assertEqual(self.store.read_records("Story Library")[0]["original_title"], "ကိုယ်ပိုင်ပုံပြင်")
        target = self.path / "backup.db"
        self.store.backup(target)
        self.assertEqual(SQLiteStore(target).read_records("Story Library"), self.store.read_records("Story Library"))

    def test_login_rate_limit_survives_new_app_client_and_unicode_password_input(self):
        for _ in range(10):
            response = self.public.post("/api/admin/login", json={"password": "မှားနေသောစကားဝှက်"})
            self.assertEqual(response.status_code, 401)
        response = web_app.app.test_client().post("/api/admin/login", json={"password": "test-password"})
        self.assertEqual(response.status_code, 429)

    def test_long_segmented_content_can_pass_content_review(self):
        story_id = self.create()
        full = "မြန်မာစာ " * 6_000
        episodes = [{"episode_number": n + 1, "title": "အပိုင်း", "content": full[i:i + 30_000]}
                    for n, i in enumerate(range(0, len(full), 30_000))]
        self.store.write_production({
            "story_id": story_id, "myanmar_title": "ရှည်သောပုံပြင်", "myanmar_story": full,
            "episodes_json": json.dumps(episodes, ensure_ascii=False),
            "quiz_json": '[{"question":"Q","answer":"A"}]', "reflection_json": '"R"',
        })
        response = self.post(f"/api/admin/story/{story_id}/content-review", {"action": "approve"})
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_azure_voice_check_ssml_escaping_and_pcm_chunk_join(self):
        with patch.dict(os.environ, {"AZURE_SPEECH_KEY": "offline-key", "AZURE_SPEECH_REGION": "eastus"}):
            provider = AzureSpeechTTS()
        voices = json.dumps([{"ShortName": "my-MM-NilarNeural", "Locale": "my-MM"}]).encode()
        with patch.object(provider, "_request", side_effect=[voices, wav_bytes(), wav_bytes()]) as request:
            data = provider.synthesize_bytes("<မြန်မာ & စာ>" + "က" * 1_000)
        with wave.open(io.BytesIO(data), "rb") as result:
            self.assertEqual(result.getnframes(), 4800)
        first_ssml = request.call_args_list[1].args[1].decode()
        self.assertIn("&lt;", first_ssml)
        self.assertIn("&amp;", first_ssml)
        with patch.object(provider, "_request", return_value=b"[]"):
            with self.assertRaises(AudioUnavailable):
                provider.synthesize_bytes("မြန်မာစာ")

    def test_gemini_tts_uses_same_key_exact_transcript_and_stateless_wav_response(self):
        with patch.dict(os.environ, {"TTS_PROVIDER": "gemini", "GEMINI_API_KEY": "offline-key"}):
            provider = configured_provider()
            self.assertIsInstance(provider, GeminiSpeechTTS)
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, limit):
                return json.dumps({"status": "completed", "steps": [{
                    "type": "model_output", "content": [{"type": "audio", "mime_type": "audio/wav",
                    "data": base64.b64encode(wav_bytes()).decode()}],
                }]}).encode()
        transcript = "<မြန်မာစာ & စမ်းသပ်ချက်>"
        with patch("pyonpyin.audio.urllib.request.urlopen", return_value=Response()) as call:
            data = provider.synthesize_bytes(transcript)
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(request.get_header("X-goog-api-key"), "offline-key")
        body = json.loads(request.data)
        self.assertEqual(body["input"][0]["content"][0]["text"], transcript)
        self.assertFalse(body["store"])
        self.assertEqual(body["model"], "gemini-3.8-flash-tts")
        self.assertEqual(body["generation_config"]["speech_config"], [{"voice": "Kore"}])
        self.assertEqual(call.call_count, 1)
        with wave.open(io.BytesIO(data), "rb") as audio:
            self.assertEqual(audio.getnframes(), 2400)

    def test_gemini_tts_chunk_join_rejects_invalid_audio_and_never_retries_http_errors(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-key"}):
            provider = GeminiSpeechTTS()
        with patch.object(provider, "_synthesize_chunk", return_value=wav_bytes()) as call:
            data = provider.synthesize_bytes("က" * 1001)
            self.assertEqual(call.call_count, 2)
        with wave.open(io.BytesIO(data), "rb") as audio:
            self.assertEqual(audio.getnframes(), 4800)
        failure = urllib.error.HTTPError("https://example.invalid", 429, "quota", None, None)
        with patch("pyonpyin.audio.urllib.request.urlopen", side_effect=failure) as call:
            with self.assertRaisesRegex(AudioUnavailable, "HTTP 429"):
                provider.synthesize_bytes("မြန်မာစာ")
            self.assertEqual(call.call_count, 1)
        class BadResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, limit):
                return b'{"steps": [{"type":"model_output","content":[{"type":"audio","data":"invalid!"}]}]}'
        with patch("pyonpyin.audio.urllib.request.urlopen", return_value=BadResponse()):
            with self.assertRaisesRegex(AudioUnavailable, "invalid speech"):
                provider.synthesize_bytes("မြန်မာစာ")

    def test_gemini_speech_queue_does_not_require_any_azure_credentials(self):
        story_id = self.create()
        self.save_draft(story_id)
        self.review(story_id)
        with patch.dict(os.environ, {"TTS_PROVIDER": "gemini", "GEMINI_API_KEY": "offline-key",
                                     "PYONPYIN_TTS_ENABLED": "true", "AZURE_SPEECH_KEY": "",
                                     "AZURE_SPEECH_REGION": ""}):
            settings = self.client.get("/api/admin/settings").get_json()
            self.assertTrue(settings["tts_configured"])
            self.assertEqual(settings["voice"], "Kore")
            response = self.post(f"/api/admin/story/{story_id}/jobs", {"kind": "AUDIO"})
            self.assertEqual(response.status_code, 202)
            with patch.object(GeminiSpeechTTS, "_synthesize_chunk", return_value=wav_bytes()):
                run_once(self.store)
        self.assertEqual(self.store.list_jobs()[0]["status"], "SUCCEEDED")
        detail = self.client.get(f"/api/admin/story/{story_id}").get_json()
        self.assertEqual(detail["production"]["audio_status"], "PENDING_REVIEW")


if __name__ == "__main__":
    unittest.main()
