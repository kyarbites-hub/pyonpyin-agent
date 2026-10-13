import json
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from pyonpyin.core import (
    candidate_category,
    eligible_candidate,
    parse_json_object,
    publication_blockers,
    safe_story_theme,
    stable_story_id,
)
from pyonpyin.gemini import GeminiClient
from scripts.gemini_smoke_test import has_myanmar_text
from pyonpyin.audio import AudioUnavailable, GoogleCloudTTS
from pyonpyin.sheets import SheetsStore
import process_stories
from process_stories import process_queued_stories
import story_finder
from story_finder import (
    cap_candidates_per_category,
    create_library_record,
    fetch_new_books,
    queue_automatic_draft,
)
from pyonpyin import web_app


class WorkflowTests(unittest.TestCase):
    def test_gemini_missing_api_key_has_clear_error_without_network_access(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(
                RuntimeError, "^Set GEMINI_API_KEY before generating story drafts\\.$"
            ):
                GeminiClient()

    def test_gemini_smoke_response_requires_myanmar_unicode(self):
        self.assertTrue(has_myanmar_text("မြန်မာစာ"))
        self.assertFalse(has_myanmar_text("English only"))
        self.assertFalse(has_myanmar_text(None))

    def test_write_production_includes_myanmar_story_quiz_and_reflection(self):
        store = SheetsStore(service=object(), spreadsheet_id="test-sheet")
        record = {
            "story_id": "pp-sheet-write",
            "myanmar_title": "ခေါင်းစဉ်",
            "myanmar_story": "ပုံပြင်",
            "episodes_json": '[{"episode_number":1}]',
            "quiz_json": '[{"question":"မေးခွန်း","answer":"အဖြေ"}]',
            "reflection_json": '["စဉ်းစားရန်"]',
        }
        with patch.object(store, "write_text", return_value=0), patch.object(
            store, "upsert"
        ) as upsert:
            store.write_production(record)
        upsert.assert_called_once()
        sheet, key, saved = upsert.call_args.args
        self.assertEqual(sheet, "Story Production")
        self.assertEqual(key, "story_id")
        for field in (
            "myanmar_story", "quiz_json", "reflection_json", "episodes_json"
        ):
            self.assertEqual(saved[field], record[field])

    def test_gemini_request_has_output_limit_and_only_one_transient_retry(self):
        client = GeminiClient(api_key="test-key")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"candidates":[{"content":{"parts":[{"text":"{\\"ok\\":true}"}]}}]}'

        unavailable = urllib.error.URLError("temporary network error")
        with patch(
            "pyonpyin.gemini.urllib.request.urlopen",
            side_effect=[unavailable, Response()],
        ) as open_url, patch("pyonpyin.gemini.time.sleep"):
            self.assertEqual(client._request("offline test prompt"), {"ok": True})
        self.assertEqual(open_url.call_count, 2)
        self.assertEqual(client.retry_count, 1)
        request = open_url.call_args_list[-1].args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 8192)
        self.assertNotIn("test-key", request.data.decode("utf-8"))

    def test_oauth_token_file_configures_sheets_credentials_without_network_access(self):
        token_data = {
            "token": "access-token-placeholder",
            "refresh_token": "refresh-token-placeholder",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id-placeholder",
            "client_secret": "client-secret-placeholder",
            "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
            "expiry": "2020-01-01T00:00:00Z",
        }
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as token_file:
            json.dump(token_data, token_file)
            token_path = token_file.name
        try:
            with patch.dict(os.environ, {
                "GOOGLE_SPREADSHEET_ID": "test-spreadsheet-id",
                "GOOGLE_TOKEN_FILE": token_path,
            }, clear=False), patch.dict(os.environ, {
                "GOOGLE_SERVICE_ACCOUNT_JSON": "",
                "GOOGLE_TOKEN_JSON": "",
            }), patch("pyonpyin.sheets.build") as build:
                service = object()
                build.return_value = service
                store = SheetsStore()
            self.assertIs(store.service, service)
            credentials = build.call_args.kwargs["credentials"]
            self.assertTrue(credentials.expired)
            self.assertTrue(credentials.refresh_token)
            self.assertEqual(
                credentials.scopes,
                ["https://www.googleapis.com/auth/spreadsheets"],
            )
            build.assert_called_once_with(
                "sheets", "v4", credentials=credentials, cache_discovery=False
            )
        finally:
            os.unlink(token_path)

    def test_story_finder_uses_google_sheets_when_token_file_is_configured(self):
        with patch.dict(os.environ, {
            "GOOGLE_SPREADSHEET_ID": "test-spreadsheet-id",
            "GOOGLE_TOKEN_FILE": "C:\\private\\token.json",
            "GOOGLE_TOKEN_JSON": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "",
        }), patch("story_finder.SheetsStore") as store_factory, patch(
            "story_finder.load_approved_sources", return_value=[]
        ):
            self.assertEqual(story_finder.main(), 0)
        store_factory.assert_called_once_with()
        store_factory.return_value.ensure_schema.assert_called_once_with()

    def test_story_finder_backfills_legacy_queued_books_without_appending_duplicates(self):
        class FakeStore:
            service = object()

            def __init__(self):
                self.library = []

            def ensure_schema(self):
                pass

            def read_records(self, _sheet):
                return []

            def upsert_story(self, record):
                self.library.append(record)

        source = {
            "source_name": "Approved source",
            "license_rule": "Verify each work",
            "feed_url": "https://example.org/feed",
        }
        books = [
            {
                "title": f"Legacy title {index}",
                "url": f"https://example.org/story/{index}",
                "source_id": f"work-{index}",
                "source_category_raw": "",
            }
            for index in range(7)
        ]
        store = FakeStore()
        with patch.dict(os.environ, {
            "GOOGLE_SPREADSHEET_ID": "test-spreadsheet-id",
            "GOOGLE_TOKEN_FILE": "C:\\private\\token.json",
            "GOOGLE_TOKEN_JSON": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "",
        }), patch("story_finder.SheetsStore", return_value=store), patch(
            "story_finder.load_approved_sources", return_value=[source]
        ), patch("story_finder.fetch_new_books", return_value=books), patch(
            "story_finder.existing_source_queue_urls",
            return_value={f"https://example.org/story/{index}" for index in range(7)},
        ), patch("story_finder.save_books_to_sheet") as save_legacy:
            self.assertEqual(story_finder.main(), 0)
        self.assertEqual(len(store.library), 5)
        self.assertTrue(all(row["category"] == "UNCLASSIFIED" for row in store.library))
        self.assertTrue(all(row["rights_cleared"] == "NO" for row in store.library))
        save_legacy.assert_not_called()

    def test_story_finder_queues_a_single_safe_draft_for_classified_discoveries(self):
        class FakeStore:
            service = object()

            def __init__(self):
                self.library = []
                self.production = []

            def ensure_schema(self):
                pass

            def read_records(self, sheet):
                return self.library if sheet == "Story Library" else self.production

            def upsert_story(self, record):
                self.library.append(record)

            def write_production(self, record):
                self.production.append(dict(record))

        store = FakeStore()
        source = {
            "source_name": "Approved source",
            "license_rule": "Verify each work",
            "feed_url": "https://example.org/feed",
        }
        book = {
            "title": "Do not send this title",
            "url": "https://example.org/story",
            "source_id": "item-1",
            "category": "CHILDREN",
            "source_category_raw": "children",
        }
        with patch.dict(os.environ, {
            "GOOGLE_SPREADSHEET_ID": "test-spreadsheet-id",
            "GOOGLE_TOKEN_FILE": "C:\\private\\token.json",
            "GOOGLE_TOKEN_JSON": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "",
        }), patch("story_finder.SheetsStore", return_value=store), patch(
            "story_finder.load_approved_sources", return_value=[source]
        ), patch("story_finder.fetch_new_books", return_value=[dict(book)]), patch(
            "story_finder.existing_source_queue_urls", return_value=set()
        ), patch("story_finder.save_books_to_sheet", return_value=1):
            self.assertEqual(story_finder.main(), 0)
        self.assertEqual(len(store.library), 1)
        self.assertEqual(len(store.production), 1)
        self.assertEqual(store.production[0]["processing_status"], "QUEUED")
        self.assertEqual(store.production[0]["draft_mode"], "ORIGINAL_THEME")

    def test_source_age_default_is_used_only_when_explicitly_configured(self):
        class FakeStore:
            service = object()

            def __init__(self):
                self.library = []
                self.production = []

            def ensure_schema(self):
                pass

            def read_records(self, sheet):
                return self.library if sheet == "Story Library" else self.production

            def upsert_story(self, record):
                self.library.append(record)

            def write_production(self, record):
                self.production.append(dict(record))

        source = {
            "source_name": "Approved source",
            "feed_url": "https://example.org/feed",
            "default_category": "ADULT",
        }
        book = {
            "title": "Story",
            "url": "https://example.org/story",
            "source_id": "story-1",
            "source_category_raw": "",
            "category": "UNCLASSIFIED",
        }
        store = FakeStore()
        with patch.dict(os.environ, {
            "GOOGLE_SPREADSHEET_ID": "test-spreadsheet-id",
            "GOOGLE_TOKEN_FILE": "C:\\private\\token.json",
            "GOOGLE_TOKEN_JSON": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "",
        }), patch("story_finder.SheetsStore", return_value=store), patch(
            "story_finder.load_approved_sources", return_value=[source]
        ), patch("story_finder.fetch_new_books", return_value=[dict(book)]), patch(
            "story_finder.existing_source_queue_urls", return_value=set()
        ), patch("story_finder.save_books_to_sheet", return_value=1):
            self.assertEqual(story_finder.main(), 0)
        self.assertEqual(store.library[0]["category"], "ADULT")
        self.assertIn("Human-approved source default", store.library[0]["category_evidence"])
        self.assertEqual(store.production[0]["draft_mode"], "ORIGINAL_THEME")

    def test_feed_text_is_exposed_only_when_verified_mode_requests_it(self):
        atom = b"""<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><id>work-1</id><title>Work</title>
        <link rel="alternate" href="https://example.org/work"/>
        <content type="html">&lt;p&gt;Full source text&lt;/p&gt;</content></entry></feed>"""

        class Response:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://example.org/feed"

            def read(self, limit):
                return atom

        with patch("story_finder.socket.getaddrinfo", return_value=[
            (None, None, None, None, ("8.8.8.8", 443))
        ]), patch("story_finder.urllib.request.urlopen", return_value=Response()):
            ordinary = fetch_new_books("https://example.org/feed")
            verified = fetch_new_books(
                "https://example.org/feed", source_configuration={
                    "approval_status": "APPROVED",
                    "automation_allowed": True,
                    "rights_policy": {
                        "mode": "VERIFIED_PUBLIC_DOMAIN",
                        "all_works_verified": True,
                        "evidence": "reviewed",
                        "jurisdiction": "Myanmar",
                        "reviewer": "Reviewer",
                        "translation_permission": "YES",
                        "ai_processing_permission": "YES",
                    },
                }
            )
        self.assertNotIn("source_text", ordinary[0])
        self.assertEqual(verified[0]["source_text"], "Full source text")

    def test_story_id_is_stable_and_url_is_a_fallback_identifier(self):
        first = stable_story_id("Standard Ebooks", "book-1", "https://example.org/a")
        second = stable_story_id("standard ebooks", "book-1", "https://example.org/b")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("pp-"))

    def test_unverified_categories_remain_unclassified_and_caps_are_independent(self):
        self.assertEqual(candidate_category("novel"), "UNCLASSIFIED")
        rows = [
            {"category": "CHILDREN", "id": number} for number in range(7)
        ] + [
            {"category": "ADULT", "id": number} for number in range(7)
        ]
        capped = cap_candidates_per_category(rows)
        self.assertEqual(sum(row["category"] == "CHILDREN" for row in capped), 5)
        self.assertEqual(sum(row["category"] == "ADULT" for row in capped), 5)

    def test_discovered_record_preserves_license_review_requirement(self):
        row = create_library_record(
            {"title": "An example", "source_url": "https://example.org/story"},
            {"source_name": "Approved source", "license_rule": "Verify the work"},
        )
        self.assertEqual(row["license_status"], "NEEDS_LICENSE_REVIEW")
        self.assertEqual(row["rights_cleared"], "NO")
        self.assertEqual(row["category"], "UNCLASSIFIED")
        self.assertTrue(row["story_id"])

    def test_unknown_rights_default_to_theme_only_without_clearing_rights(self):
        row = create_library_record(
            {
                "title": "Do not send this title",
                "source_url": "https://example.org/story",
                "category": "CHILDREN",
                "category_evidence": "Feed audience classification",
            },
            {"source_name": "Unknown source"},
        )
        self.assertEqual(row["rights_mode"], "UNKNOWN")
        self.assertEqual(row["license_status"], "NEEDS_LICENSE_REVIEW")
        self.assertEqual(row["rights_cleared"], "NO")
        self.assertEqual(row["broad_theme"], "kindness")
        self.assertTrue(queue_automatic_draft(type("Store", (), {
            "write_production": lambda _self, record: setattr(_self, "queued", record),
        })(), row, []))

    def test_public_domain_automation_requires_explicit_source_policy(self):
        source = {
            "source_name": "Policy-reviewed source",
            "approval_status": "APPROVED",
            "automation_allowed": True,
            "rights_policy": {
                "mode": "VERIFIED_PUBLIC_DOMAIN",
                "all_works_verified": True,
                "evidence": "Reviewed catalogue and rights basis",
                "jurisdiction": "Myanmar",
                "reviewer": "Source reviewer",
                "translation_permission": "YES",
                "ai_processing_permission": "YES",
            },
        }
        row = create_library_record({
            "title": "Work",
            "source_url": "https://example.org/work",
            "category": "ADULT",
            "category_evidence": "Feed audience classification",
            "source_text": "Verified full work text",
        }, source)
        self.assertEqual(row["rights_mode"], "VERIFIED_PUBLIC_DOMAIN")
        self.assertEqual(row["rights_cleared"], "YES")
        self.assertTrue(eligible_candidate(row))
        queue_store = type("Store", (), {
            "write_production": lambda _self, record: setattr(_self, "queued", record),
        })()
        self.assertTrue(queue_automatic_draft(queue_store, row, []))
        self.assertEqual(queue_store.queued["draft_mode"], "PUBLIC_DOMAIN_RETELLING")

        source["rights_policy"]["evidence"] = ""
        unverified = create_library_record({
            "title": "Work",
            "source_url": "https://example.org/work",
            "category": "ADULT",
            "category_evidence": "Feed audience classification",
            "source_text": "Must not be retained when rights are unknown",
        }, source)
        self.assertEqual(unverified["rights_mode"], "UNKNOWN")
        self.assertEqual(unverified["rights_cleared"], "NO")
        self.assertEqual(unverified["source_text"], "")

        source["rights_policy"]["evidence"] = None
        no_evidence = create_library_record({
            "title": "Work",
            "source_url": "https://example.org/work",
            "category": "ADULT",
            "category_evidence": "Feed audience classification",
            "source_text": "Must not be retained",
        }, source)
        self.assertEqual(no_evidence["rights_mode"], "UNKNOWN")
        self.assertEqual(no_evidence["source_text"], "")

    def test_auto_queue_skips_unknown_categories_and_existing_production(self):
        row = create_library_record(
            {
                "title": "Work",
                "source_url": "https://example.org/work",
                "category_evidence": "Feed audience classification",
            },
            {"source_name": "Source"},
        )
        store = type("Store", (), {"write_production": lambda *_args: self.fail(
            "ineligible story must not be queued"
        )})()
        self.assertFalse(queue_automatic_draft(store, row, []))
        row["category"] = "ADULT"
        self.assertFalse(queue_automatic_draft(
            store, row, [{"story_id": row["story_id"], "processing_status": "DRAFT_READY"}]
        ))

    def test_theme_allowlist_rejects_arbitrary_feed_text(self):
        self.assertEqual(safe_story_theme("CHILDREN", "friendship"), "friendship")
        self.assertEqual(
            safe_story_theme("CHILDREN", "Existing book plot and characters"),
            "kindness",
        )
        self.assertEqual(safe_story_theme("UNCLASSIFIED", "courage"), "")

    def test_rights_gate_requires_explicit_evidence_and_reviewer(self):
        incomplete = {
            "category": "ADULT",
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "human_reviewer": "",
            "license_evidence": "license URL",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
        }
        self.assertFalse(eligible_candidate(incomplete))
        self.assertTrue(eligible_candidate({
            **incomplete,
            "human_reviewer": "Reviewer",
        }))

    def test_publication_blocks_incomplete_or_mismatched_episodes(self):
        story = {
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "human_reviewer": "Reviewer",
            "license_evidence": "https://example.org/license",
            "rights_jurisdiction": "Myanmar",
            "content_review_status": "APPROVED",
            "approval_status": "APPROVED",
            "myanmar_story": "စမ်းသပ် ပုံပြင်",
            "myanmar_title": "ခေါင်းစဉ်",
            "category": "CHILDREN",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "permission_for_publication": "YES",
            "permission_for_audio": "YES",
            "permission_for_audio": "YES",
        }
        episodes = [
            {"episode_number": "1", "title": "အပိုင်း ၁", "content": "စမ်းသပ် "},
            {"episode_number": "2", "title": "အပိုင်း ၂", "content": "ပုံပြင်"},
        ]
        self.assertEqual(publication_blockers(story, episodes), [])
        episodes[1]["episode_number"] = "3"
        self.assertTrue(publication_blockers(story, episodes))

    def test_required_audio_is_a_publication_gate(self):
        story = {
            "license_status": "APPROVED", "rights_cleared": "YES",
            "human_reviewer": "Reviewer", "license_evidence": "Evidence",
            "rights_jurisdiction": "Myanmar",
            "content_review_status": "APPROVED", "approval_status": "APPROVED",
            "myanmar_story": "story",
            "myanmar_title": "title",
            "category": "CHILDREN",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "permission_for_publication": "YES",
        }
        episodes = [{"episode_number": "1", "title": "one", "content": "story"}]
        self.assertTrue(publication_blockers(story, episodes, require_audio=True))
        story.update({"audio_url": "https://cdn.example/audio.mp3", "audio_status": "READY"})
        story["permission_for_audio"] = "YES"
        self.assertEqual(publication_blockers(story, episodes, require_audio=True), [])
        story["audio_url"] = "javascript:alert(1)"
        self.assertTrue(publication_blockers(story, episodes, require_audio=True))

    def test_gemini_never_sends_story_without_rights_clearance(self):
        client = GeminiClient(api_key="test-key")
        with patch.object(client, "_request") as request:
            with self.assertRaises(PermissionError):
                client.generate_draft(
                    {"license_status": "NEEDS_LICENSE_REVIEW"}, "private story"
                )
        request.assert_not_called()

    def test_theme_draft_never_sends_source_text_or_discovered_title(self):
        client = GeminiClient(api_key="test-key")
        story = {
            "draft_mode": "ORIGINAL_THEME",
            "category": "CHILDREN",
            "broad_theme": "friendship",
            "original_title": "Copyrighted discovery title",
        }
        output = {
            "title": "ခေါင်းစဉ်",
            "story": "ပုံပြင်",
            "episodes": [
                {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
            ],
            "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
            "reflection": "စဉ်းစားရန်",
        }
        with patch.object(client, "_request", return_value=output) as request:
            self.assertEqual(
                client.generate_draft(story, "")["title"],
                "ခေါင်းစဉ်",
            )
        prompt = request.call_args.args[0]
        self.assertIn("completely original", prompt)
        self.assertIn("friendship", prompt)
        self.assertNotIn("Copyrighted discovery title", prompt)
        self.assertNotIn("source story", prompt)

        with patch.object(client, "_request") as request:
            with self.assertRaisesRegex(PermissionError, "Source text cannot be sent"):
                client.generate_draft(story, "private copyrighted text")
        request.assert_not_called()

    def test_public_domain_retelling_prompt_requires_rights_and_avoids_close_copy(self):
        client = GeminiClient(api_key="test-key")
        story = {
            "draft_mode": "PUBLIC_DOMAIN_RETELLING",
            "category": "ADULT",
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "human_reviewer": "Reviewer",
            "license_evidence": "Evidence",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
        }
        output = {
            "title": "ခေါင်းစဉ်",
            "story": "ပုံပြင်",
            "episodes": [
                {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
            ],
            "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
            "reflection": "စဉ်းစားရန်",
        }
        with patch.object(client, "_request", return_value=output) as request:
            client.generate_draft(story, "cleared source")
        self.assertIn("genuinely original Myanmar retelling", request.call_args.args[0])
        self.assertIn("cleared source", request.call_args.args[0])

    def test_disabled_automation_does_not_connect_to_google_sheets(self):
        with patch.dict(os.environ, {"PYONPYIN_GEMINI_AUTOMATION_ENABLED": "false"}), \
                patch("process_stories.SheetsStore") as store_factory:
            self.assertEqual(process_stories.main(), 0)
        store_factory.assert_not_called()

    def test_gemini_validates_episode_partition_and_structured_quiz(self):
        client = GeminiClient(api_key="test-key")
        story = {
            "category": "CHILDREN",
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "human_reviewer": "Reviewer",
            "license_evidence": "License",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
        }
        output = {
            "title": "ခေါင်းစဉ်",
            "story": "စမ်းသပ် ပုံပြင်",
            "episodes": [
                {"episode_number": 1, "title": "တစ်", "content": "စမ်းသပ် "},
                {"episode_number": 2, "title": "နှစ်", "content": "ပုံပြင်"},
            ],
            "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
            "reflection": "စဉ်းစားရန်",
        }
        with patch.object(client, "_request", return_value=output):
            self.assertEqual(client.generate_draft(story, "source")["title"], "ခေါင်းစဉ်")
        output["episodes"][1]["content"] = "ပျောက်နေသည်"
        with patch.object(client, "_request", return_value=output):
            with self.assertRaisesRegex(RuntimeError, "partition"):
                client.generate_draft(story, "source")

    def test_pipeline_processes_only_explicitly_queued_rights_cleared_story(self):
        story = {
            "story_id": "pp-process", "category": "CHILDREN",
            "license_status": "APPROVED", "rights_cleared": "YES",
            "human_reviewer": "Reviewer", "license_evidence": "License",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
        }
        production = {"story_id": "pp-process", "processing_status": "QUEUED"}

        class FakeStore:
            def __init__(self):
                self.production = dict(production)
                self.history = []
                self.episodes = []

            def read_records(self, sheet):
                return [story] if sheet == "Story Library" else [self.production]

            def read_texts(self, _text_type):
                return {"pp-process": "original"}

            def write_production(self, row):
                self.production.update(row)

            def write_episodes(self, story_id, episodes):
                self.episodes = list(episodes)

            def record_processing(self, row):
                self.history.append(row)

        class FakeGemini:
            model = "test-model"
            retry_count = 0

            def generate_draft(self, _story, _source):
                return {
                    "title": "ခေါင်းစဉ်",
                    "story": "ပုံပြင်",
                    "episodes": [
                        {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
                    ],
                    "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
                    "reflection": "စဉ်းစားရန်",
                }

        store = FakeStore()
        self.assertEqual(process_queued_stories(store, FakeGemini()), 0)
        self.assertEqual(store.production["processing_status"], "DRAFT_READY")
        self.assertEqual(len(store.episodes), 1)
        self.assertEqual(store.history[0]["status"], "DRAFT_READY")

        story["permission_for_ai_processing"] = "NO"
        store = FakeStore()
        self.assertEqual(process_queued_stories(store, FakeGemini()), 1)
        self.assertEqual(store.production["processing_status"], "BLOCKED_RIGHTS")
        self.assertEqual(store.history[0]["status"], "BLOCKED_RIGHTS")

    def test_pipeline_generates_original_theme_draft_without_reading_source_or_rights_clearance(self):
        story = {
            "story_id": "pp-theme",
            "category": "CHILDREN",
            "original_title": "Do not pass this title to Gemini",
            "rights_mode": "UNKNOWN",
            "rights_cleared": "NO",
            "broad_theme": "friendship",
            "source_text": "Do not pass this source text to Gemini",
        }
        production = {
            "story_id": "pp-theme",
            "draft_mode": "ORIGINAL_THEME",
            "processing_status": "QUEUED",
        }

        class FakeStore:
            def __init__(self):
                self.production = dict(production)
                self.history = []
                self.episodes = []

            def read_records(self, sheet):
                return [story] if sheet == "Story Library" else [self.production]

            def read_texts(self, _text_type):
                self.fail("theme-only generation must not read the source text sheet")

            def write_production(self, row):
                self.production.update(row)

            def write_episodes(self, _story_id, episodes):
                self.episodes = list(episodes)

            def record_processing(self, row):
                self.history.append(row)

        class FakeGemini:
            model = "test-model"
            retry_count = 0

            def generate_draft(inner_self, story_data, source_text):
                self.assertEqual(source_text, "")
                self.assertNotIn("source_text", story_data)
                self.assertNotIn("original_title", story_data)
                self.assertEqual(story_data["broad_theme"], "friendship")
                return {
                    "title": "ခေါင်းစဉ်",
                    "story": "ပုံပြင်",
                    "episodes": [
                        {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
                    ],
                    "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
                    "reflection": "စဉ်းစားရန်",
                }

        store = FakeStore()
        self.assertEqual(process_queued_stories(store, FakeGemini()), 0)
        self.assertEqual(store.production["processing_status"], "DRAFT_READY")
        self.assertEqual(store.production["license_review_status"], "NOT_USED_THEME_ONLY")
        self.assertEqual(store.production["quiz_json"], '[{"question": "မေးခွန်း", "answer": "အဖြေ"}]')
        self.assertEqual(len(store.episodes), 1)

    def test_processing_default_limit_is_one_draft_per_run(self):
        library = [
            {
                "story_id": f"pp-{index}",
                "category": "ADULT",
                "rights_mode": "UNKNOWN",
                "broad_theme": "resilience",
            }
            for index in range(2)
        ]
        production = [
            {
                "story_id": row["story_id"],
                "draft_mode": "ORIGINAL_THEME",
                "processing_status": "QUEUED",
            }
            for row in library
        ]

        class FakeStore:
            def read_records(self, sheet):
                return library if sheet == "Story Library" else production

            def read_texts(self, _text_type):
                raise AssertionError("Theme drafts must not read source text.")

            def write_production(self, update):
                next(row for row in production if row["story_id"] == update["story_id"]).update(update)

            def write_episodes(self, _story_id, _episodes):
                pass

            def record_processing(self, _record):
                pass

        class FakeGemini:
            model = "test-model"
            retry_count = 0

            def __init__(self):
                self.calls = 0

            def generate_draft(self, _story, _source):
                self.calls += 1
                return {
                    "title": "ခေါင်းစဉ်",
                    "story": "ပုံပြင်",
                    "episodes": [
                        {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
                    ],
                    "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
                    "reflection": "စဉ်းစားရန်",
                }

        client = FakeGemini()
        self.assertEqual(process_queued_stories(FakeStore(), client), 0)
        self.assertEqual(client.calls, 1)
        self.assertEqual(production[0]["processing_status"], "DRAFT_READY")
        self.assertEqual(production[1]["processing_status"], "QUEUED")

    def test_unverified_audio_adapter_fails_without_a_network_request(self):
        provider = GoogleCloudTTS(api_key="not-used", voice="my-MM-Standard-A")
        with patch("pyonpyin.audio.urllib.request.urlopen") as open_url, self.assertRaises(AudioUnavailable):
            provider.synthesize("မြန်မာစာ", "sample.mp3")
        open_url.assert_not_called()

    def test_json_response_parser_accepts_fenced_json(self):
        self.assertEqual(parse_json_object("```json\n{\"ok\": true}\n```"), {"ok": True})

    def test_atom_feed_metadata_is_captured_without_mistaking_license_link_for_story(self):
        atom = b"""<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><id>book-42</id><title>Sample</title>
        <author><name>Author</name></author><published>1900-01-01</published>
        <category term="mystery"/>
        <link rel="license" href="https://example.org/license"/>
        <link rel="alternate" href="https://example.org/book"/></entry></feed>"""

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://example.org/feed"

            def read(self, limit):
                return atom

        with patch("story_finder.socket.getaddrinfo", return_value=[
            (None, None, None, None, ("8.8.8.8", 443))
        ]), patch("story_finder.urllib.request.urlopen", return_value=Response()):
            books = fetch_new_books("https://example.org/feed")
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["url"], "https://example.org/book")
        self.assertEqual(books[0]["source_id"], "book-42")
        self.assertEqual(books[0]["author"], "Author")
        self.assertEqual(books[0]["license_url"], "https://example.org/license")
        self.assertEqual(books[0]["category"], "UNCLASSIFIED")

    def test_feed_rejects_non_https_urls_without_network_access(self):
        with patch("story_finder.urllib.request.urlopen") as open_url:
            self.assertEqual(fetch_new_books("http://example.org/feed"), [])
        open_url.assert_not_called()

    def test_sheet_upsert_preserves_columns_not_in_a_partial_update(self):
        class Request:
            def __init__(self, result=None):
                self.result = result or {}
                self.writes = []

            def execute(self):
                return self.result

        class Values:
            def __init__(self):
                self.updated = None

            def get(self, **kwargs):
                return Request({"values": [
                    ["story_id", "myanmar_title", "approval_status"],
                    ["pp-1", "Existing title", "APPROVED"],
                ]})

            def update(self, **kwargs):
                self.updated = kwargs
                return Request()

            def batchUpdate(self, **kwargs):
                self.updated = kwargs
                return Request()

            def append(self, **kwargs):
                self.updated = kwargs
                return Request()

        class Spreadsheets:
            def __init__(self):
                self.value_api = Values()

            def values(self):
                return self.value_api

        class Service:
            def __init__(self):
                self.api = Spreadsheets()

            def spreadsheets(self):
                return self.api

        service = Service()
        SheetsStore(service=service, spreadsheet_id="sheet-id").upsert(
            "Story Production", "story_id",
            {"story_id": "pp-1", "myanmar_title": "Updated title"},
        )
        self.assertEqual(
            service.api.value_api.updated["body"]["data"][0]["values"],
            [["pp-1", "Updated title", "APPROVED"]],
        )

    def test_long_sheet_text_is_chunked_and_reconstructed_without_stale_segments(self):
        store = SheetsStore.__new__(SheetsStore)
        records = []

        def read_records(_sheet):
            return records

        def upsert_many(_sheet, key_column, updates):
            for update in updates:
                previous = next(
                    (row for row in records if row.get(key_column) == update[key_column]),
                    None,
                )
                if previous is None:
                    records.append(dict(update))
                else:
                    previous.update(update)
            return []

        store.read_records = read_records
        store.upsert_many = upsert_many
        long_text = "ပုံပြင်" * 8_000
        self.assertEqual(store.write_text("pp-long", "MYANMAR", long_text), 2)
        self.assertEqual(store.read_texts("MYANMAR")["pp-long"], long_text)
        self.assertEqual(store.write_text("pp-long", "MYANMAR", "အသစ်"), 0)
        self.assertNotIn("pp-long", store.read_texts("MYANMAR"))
        self.assertTrue(all(row["active"] == "NO" for row in records))

    def test_default_publication_configuration_is_disabled(self):
        story_id = "pp-test"
        library = {
            "story_id": story_id, "category": "CHILDREN",
            "license_status": "APPROVED", "rights_cleared": "YES",
            "human_reviewer": "Reviewer", "license_evidence": "Evidence",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "permission_for_publication": "YES",
        }
        production = {
            "story_id": story_id, "myanmar_title": "ခေါင်းစဉ်",
            "myanmar_story": "ပုံပြင်", "episodes_json": json.dumps([
                {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
            ], ensure_ascii=False),
            "content_review_status": "APPROVED", "approval_status": "APPROVED",
            "audio_required": "NO",
        }

        class FakeStore:
            publication_records = []

            def ensure_schema(self):
                pass

            def read_records(self, sheet):
                if sheet == "Story Library":
                    return [library]
                if sheet == "Story Production":
                    return [production]
                if sheet == "Story Episodes":
                    return [{
                        "story_id": story_id, "episode_number": "1",
                        "title": "အပိုင်း ၁", "content": "ပုံပြင်", "complete": "YES",
                    }]
                return []

            def read_texts(self, _text_type):
                return {}

            def record_publication(self, record):
                self.publication_records.append(record)

        store = FakeStore()
        with patch.object(web_app, "_store", return_value=store), patch.dict(
            os.environ, {"PYONPYIN_PUBLISHING_ENABLED": "false"}
        ):
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "test-token"
            response = client.post(
                f"/admin/story/{story_id}/publish",
                data={
                    "csrf_token": "test-token",
                    "content_review_status": "APPROVED",
                    "approval_status": "APPROVED",
                    "approved_by": "Reviewer",
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(store.publication_records[-1]["publication_status"], "DISABLED")

    def test_publication_requires_explicit_approval_even_when_enabled(self):
        story_id = "pp-approval-required"
        library = {
            "story_id": story_id, "category": "CHILDREN",
            "license_status": "APPROVED", "rights_cleared": "YES",
            "human_reviewer": "Rights reviewer", "license_evidence": "Evidence",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "permission_for_publication": "YES",
        }
        production = {
            "story_id": story_id, "myanmar_title": "ခေါင်းစဉ်",
            "myanmar_story": "ပုံပြင်",
            "content_review_status": "APPROVED",
            "audio_required": "NO",
        }
        episode = {
            "story_id": story_id, "episode_number": "1",
            "title": "အပိုင်း ၁", "content": "ပုံပြင်", "complete": "YES",
        }

        class FakeStore:
            def __init__(self):
                self.publications = []
                self.production_writes = []

            def ensure_schema(self):
                pass

            def read_records(self, sheet):
                if sheet == "Story Library":
                    return [library]
                if sheet == "Story Production":
                    return [production]
                if sheet == "Story Episodes":
                    return [episode]
                return []

            def read_texts(self, _text_type):
                return {}

            def record_publication(self, record):
                self.publications.append(record)

            def write_production(self, record):
                self.production_writes.append(record)

        store = FakeStore()
        with patch.object(web_app, "_store", return_value=store), patch.dict(
            os.environ, {"PYONPYIN_PUBLISHING_ENABLED": "true"}
        ):
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "test-token"
            response = client.post(
                f"/admin/story/{story_id}/publish",
                data={
                    "csrf_token": "test-token",
                    "content_review_status": "APPROVED",
                    "approved_by": "Publisher",
                },
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(store.publications[-1]["publication_status"], "BLOCKED")
        self.assertEqual(store.production_writes, [])

    def test_public_api_never_returns_private_source_text(self):
        story_id = "pp-public"
        library = {
            "story_id": story_id, "category": "CHILDREN",
            "source_text": "PRIVATE ORIGINAL SOURCE",
            "license_status": "APPROVED", "rights_cleared": "YES",
            "rights_jurisdiction": "Myanmar",
            "human_reviewer": "Reviewer", "license_evidence": "Evidence",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "permission_for_publication": "YES",
        }
        production = {
            "story_id": story_id, "myanmar_title": "ခေါင်းစဉ်",
            "myanmar_story": "ပုံပြင်",
            "episodes_json": json.dumps([
                {"episode_number": 1, "title": "အပိုင်း ၁", "content": "ပုံပြင်"}
            ], ensure_ascii=False),
            "content_review_status": "APPROVED", "approval_status": "APPROVED",
            "audio_required": "NO",
        }

        class FakeStore:
            def ensure_schema(self):
                pass

            def read_records(self, sheet):
                if sheet == "Story Library":
                    return [library]
                if sheet == "Story Production":
                    return [production]
                return [{
                    "story_id": story_id,
                    "publication_status": "PUBLISHED",
                }]

            def read_texts(self, _text_type):
                return {}

        with patch.object(web_app, "_store", return_value=FakeStore()):
            response = web_app.app.test_client().get("/api/stories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["story"], "ပုံပြင်")
        self.assertNotIn("source_text", response.get_data(as_text=True))

    def test_dashboard_requires_authentication_and_sets_security_headers(self):
        class FakeStore:
            def ensure_schema(self):
                pass

            def read_records(self, _sheet):
                return []

            def read_texts(self, _text_type):
                return {}

        with patch.object(web_app, "_store", return_value=FakeStore()):
            client = web_app.app.test_client()
            denied = client.get("/admin")
            self.assertEqual(denied.status_code, 302)
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
            response = client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", response.headers)

    def test_public_site_renders_category_navigation(self):
        class FakeStore:
            def read_records(self, _sheet):
                return []

            def read_texts(self, _text_type):
                return {}

        with patch.object(web_app, "_store", return_value=FakeStore()):
            response = web_app.app.test_client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("children", response.get_data(as_text=True))
        self.assertIn("adult", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
