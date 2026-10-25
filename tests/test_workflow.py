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
from process_stories import process_queued_stories, queue_eligible_stories
import story_finder
from story_finder import (
    cap_candidates_per_category,
    create_library_record,
    fetch_new_books,
    queue_automatic_draft,
)
from pyonpyin import web_app


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # Keep legacy mocked Sheets tests independent of the developer's local MVP .env/database.
        environment = patch.dict(os.environ, {
            "PYONPYIN_STORAGE": "sheets", "PYONPYIN_ENV_FILE": "tests/nonexistent-offline.env",
        })
        environment.start()
        self.addCleanup(environment.stop)

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

    def test_sheets_upsert_many_coalesces_duplicate_keys_and_preserves_existing_columns(self):
        store = SheetsStore(service=object(), spreadsheet_id="test-sheet")

        class Values:
            def get(self, **_kwargs):
                return {"operation": "get"}

            def batchUpdate(self, **kwargs):
                return {"operation": "update", **kwargs}

            def append(self, **kwargs):
                return {"operation": "append", **kwargs}

        values = Values()
        def execute(request):
            if request["operation"] == "get":
                return {"values": [
                    ["story_id", "title", "license_evidence"],
                    ["existing", "Old title", "human evidence"],
                ]}
            return request

        with patch.object(store, "_values", return_value=values), patch.object(
            store, "_execute", side_effect=execute,
        ) as execute:
            rows = store.upsert_many("Story Library", "story_id", [
                {"story_id": "existing", "title": "Updated title"},
                {"story_id": "new-story", "title": "First value"},
                {"story_id": "new-story", "title": "Final value"},
            ])

        self.assertEqual(rows, [2, 3])
        self.assertEqual(execute.call_count, 3)
        update_request = execute.call_args_list[1].args[0]
        append_request = execute.call_args_list[2].args[0]
        self.assertEqual(
            update_request["body"]["data"][0]["values"],
            [["existing", "Updated title", "human evidence"]],
        )
        self.assertEqual(
            append_request["body"]["values"],
            [["new-story", "Final value", ""]],
        )

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
            rebuilt = client.generate_draft(story, "source")
            self.assertEqual(rebuilt["story"], "စမ်းသပ် ပုံပြင်")
            self.assertEqual("".join(ep["content"] for ep in rebuilt["episodes"]), rebuilt["story"])
            self.assertTrue(rebuilt["episode_partition_rebuilt"])

    def test_gemini_episode_reconstruction_preserves_long_story_and_cell_limits(self):
        client = GeminiClient(api_key="test-key")
        full_story = "မြန်မာပုံပြင်။ " * 4_000
        output = {
            "title": "ရှည်သောပုံပြင်", "story": full_story,
            "episodes": [{"episode_number": 1, "title": "အပိုင်း", "content": "မတူသောစာသား"}],
            "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}], "reflection": "စဉ်းစားရန်",
        }
        with patch.object(client, "_request", return_value=output):
            result = client.generate_draft({"category": "CHILDREN", "draft_mode": "ORIGINAL_THEME"}, "")
        self.assertEqual("".join(ep["content"] for ep in result["episodes"]), full_story)
        self.assertTrue(all(0 < len(ep["content"]) <= 40_000 for ep in result["episodes"]))
        self.assertGreater(len(result["episodes"]), 1)
        self.assertEqual([ep["episode_number"] for ep in result["episodes"]], list(range(1, len(result["episodes"]) + 1)))

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

    def test_pipeline_dispatch_target_processes_only_the_requested_dispatched_story(self):
        def eligible_story(story_id):
            return {
                "story_id": story_id,
                "category": "CHILDREN",
                "license_status": "APPROVED",
                "rights_cleared": "YES",
                "human_reviewer": "Reviewer",
                "license_evidence": "Evidence",
                "rights_jurisdiction": "Myanmar",
                "permission_for_translation": "YES",
                "permission_for_ai_processing": "YES",
            }

        stories = [eligible_story("pp-dispatched"), eligible_story("pp-next")]
        production = [
            {"story_id": "pp-dispatched", "processing_status": "DISPATCHED"},
            {"story_id": "pp-next", "processing_status": "QUEUED"},
        ]

        class FakeStore:
            def __init__(self):
                self.production = [dict(row) for row in production]
                self.writes = []
                self.episodes = []

            def read_records(self, sheet):
                return stories if sheet == "Story Library" else self.production

            def read_texts(self, _text_type):
                return {"pp-dispatched": "source"}

            def write_production(self, row):
                target = next(item for item in self.production if item["story_id"] == row["story_id"])
                target.update(row)
                self.writes.append(dict(row))

            def write_episodes(self, _story_id, episodes):
                self.episodes.extend(episodes)

            def record_processing(self, _row):
                pass

        class FakeGemini:
            model = "offline-model"
            retry_count = 0

            def __init__(self):
                self.called_story_ids = []

            def generate_draft(self, story, _source):
                self.called_story_ids.append(story["story_id"])
                return {
                    "title": "ခေါင်းစဉ်",
                    "story": "ပုံပြင်",
                    "episodes": [{"episode_number": 1, "title": "အပိုင်း", "content": "ပုံပြင်"}],
                    "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
                    "reflection": "စဉ်းစားရန်",
                }

        store = FakeStore()
        client = FakeGemini()
        self.assertEqual(
            process_queued_stories(store, client, target_story_id="pp-dispatched"),
            0,
        )
        self.assertEqual(client.called_story_ids, ["pp-dispatched"])
        self.assertEqual(
            next(row for row in store.production if row["story_id"] == "pp-next")[
                "processing_status"
            ],
            "QUEUED",
        )

    def test_queue_eligible_library_records_uses_safe_policy_and_preserves_existing_rows(self):
        verified_story = {
            "story_id": "pp-verified",
            "category": "ADULT",
            "category_evidence": "Explicit feed audience category",
            "rights_mode": "VERIFIED_PUBLIC_DOMAIN",
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "license_evidence": "Verified work-level rights record",
            "human_reviewer": "Reviewer",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "source_text": "Public-domain source text",
        }
        unknown_rights_story = {
            "story_id": "pp-theme-queued",
            "category": "CHILDREN",
            "category_evidence": "Explicit feed audience category",
            "rights_mode": "UNKNOWN",
            "license_status": "UNKNOWN",
            "rights_cleared": "NO",
            "broad_theme": "friendship",
            "original_title": "Must not be sent to Gemini",
            "source_text": "Must not be sent to Gemini",
        }
        unclassified_story = {
            "story_id": "pp-unclassified",
            "category": "UNCLASSIFIED",
            "category_evidence": "No source age-category evidence",
            "rights_mode": "UNKNOWN",
        }
        existing_draft = {
            "story_id": "pp-existing",
            "processing_status": "DRAFT_READY",
            "myanmar_title": "Keep this draft",
        }

        class FakeStore:
            def __init__(self):
                self.writes = []

            def write_production(self, row):
                self.writes.append(dict(row))

        store = FakeStore()
        production_rows = [existing_draft]
        queued_count = queue_eligible_stories(
            store,
            [verified_story, unknown_rights_story, unclassified_story],
            production_rows,
        )

        self.assertEqual(queued_count, 2)
        self.assertEqual(
            [(row["story_id"], row["draft_mode"]) for row in store.writes],
            [
                ("pp-verified", "PUBLIC_DOMAIN_RETELLING"),
                ("pp-theme-queued", "ORIGINAL_THEME"),
            ],
        )
        self.assertEqual(production_rows[0], existing_draft)
        self.assertEqual(
            [row["story_id"] for row in production_rows],
            ["pp-existing", "pp-verified", "pp-theme-queued"],
        )
        self.assertEqual(store.writes[1]["approval_status"], "")
        self.assertNotIn("pp-unclassified", [row["story_id"] for row in production_rows])

        self.assertEqual(
            queue_eligible_stories(
                store,
                [verified_story, unknown_rights_story, unclassified_story],
                production_rows,
            ),
            0,
        )
        self.assertEqual(len(store.writes), 2)

    def test_pipeline_generates_original_theme_draft_without_reading_source_or_rights_clearance(self):
        story = {
            "story_id": "pp-theme",
            "category": "CHILDREN",
            "category_evidence": "Explicit feed audience category",
            "original_title": "Do not pass this title to Gemini",
            "rights_mode": "UNKNOWN",
            "rights_cleared": "NO",
            "broad_theme": "friendship",
            "source_text": "Do not pass this source text to Gemini",
        }

        class FakeStore:
            def __init__(self):
                self.production = []
                self.history = []
                self.episodes = []

            def read_records(self, sheet):
                return [story] if sheet == "Story Library" else self.production

            def read_texts(self, _text_type):
                self.fail("theme-only generation must not read the source text sheet")

            def write_production(self, row):
                existing = next(
                    (item for item in self.production if item["story_id"] == row["story_id"]),
                    None,
                )
                if existing:
                    existing.update(row)
                else:
                    self.production.append(dict(row))

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
        self.assertEqual(store.production[0]["processing_status"], "DRAFT_READY")
        self.assertEqual(store.production[0]["draft_mode"], "ORIGINAL_THEME")
        self.assertEqual(store.production[0]["license_review_status"], "NOT_USED_THEME_ONLY")
        self.assertEqual(store.production[0]["quiz_json"], '[{"question": "မေးခွန်း", "answer": "အဖြေ"}]')
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
                {
                    "episode_number": 1,
                    "title": "အပိုင်း ၁",
                    "content": "ပုံပြင်",
                    "audio_url": "https://audio.example/unreviewed.mp3",
                    "audio_status": "NOT_READY",
                }
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
        self.assertEqual(response.json[0]["episodes"][0]["audio_url"], "")
        self.assertNotIn("unreviewed.mp3", response.get_data(as_text=True))
        self.assertNotIn("source_text", response.get_data(as_text=True))

    def test_admin_api_requires_session_and_returns_only_review_metadata(self):
        story = {
            "story_id": "pp-admin-api",
            "original_title": "Review fixture",
            "source_text": "PRIVATE SOURCE TEXT",
            "source_url": "https://example.org/private-work",
            "source_name": "Fixture source",
            "category": "UNCLASSIFIED",
            "category_evidence": "No reliable evidence",
            "license_status": "NEEDS_LICENSE_REVIEW",
            "rights_cleared": "NO",
            "review_status": "PENDING_REVIEW",
            "license_evidence": "",
            "rights_jurisdiction": "",
            "human_reviewer": "",
        }
        production = {
            "story_id": "pp-admin-api",
            "processing_status": "NOT_QUEUED",
            "processing_error": "",
            "approval_status": "",
            "content_review_status": "PENDING",
            "audio_status": "NOT_READY",
        }
        class FakeStore:
            def read_records(self, sheet):
                if sheet == "Story Library":
                    return [story]
                if sheet == "Story Production":
                    return [production]
                if sheet == "Publishing History":
                    return []
                return []

        with patch.object(web_app, "_store", return_value=FakeStore()):
            client = web_app.app.test_client()
            self.assertEqual(client.get("/api/admin/overview").status_code, 401)
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
            response = client.get("/api/admin/overview")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["counts"]["stories"], 1)
        self.assertEqual(response.json["counts"]["rights_review"], 1)
        self.assertEqual(response.json["stories"][0]["category"], "UNCLASSIFIED")
        self.assertNotIn("source_text", response.get_data(as_text=True))
        self.assertNotIn("GEMINI_API_KEY", response.get_data(as_text=True))
        self.assertNotIn("PRIVATE SOURCE TEXT", response.get_data(as_text=True))

    def test_admin_api_login_uses_existing_password_session_and_csrf_protection(self):
        with patch.dict(os.environ, {
            "PYONPYIN_ADMIN_PASSWORD": "offline-test-password",
            "PYONPYIN_SESSION_SECRET": "offline-test-session-secret",
        }):
            client = web_app.app.test_client()
            denied = client.post(
                "/api/admin/login",
                json={"password": "wrong-password"},
            )
            self.assertEqual(denied.status_code, 401)
            accepted = client.post(
                "/api/admin/login",
                json={"password": "offline-test-password"},
            )
            self.assertEqual(accepted.status_code, 200)
            csrf_token = accepted.json["csrf_token"]
            missing_csrf = client.post("/api/admin/logout")
            self.assertEqual(missing_csrf.status_code, 400)
            logged_out = client.post(
                "/api/admin/logout",
                headers={"X-CSRF-Token": csrf_token},
            )
            self.assertEqual(logged_out.status_code, 200)
            self.assertEqual(client.get("/api/admin/jobs").status_code, 401)

    def test_admin_login_preflight_allows_only_project_vercel_origins_and_credentials(self):
        origin = "https://pyonpyin-agent-frontend-c1wksdnc8-kyarbites.vercel.app"
        with patch.dict(os.environ, {
            "PYONPYIN_ADMIN_PASSWORD": "offline-test-password",
            "PYONPYIN_SESSION_SECRET": "offline-test-session-secret",
            "PYONPYIN_HTTPS": "true",
        }):
            client = web_app.app.test_client()
            preflight = client.options(
                "/api/admin/login",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            self.assertEqual(preflight.status_code, 200)
            self.assertEqual(preflight.headers["Access-Control-Allow-Origin"], origin)
            self.assertEqual(
                preflight.headers["Access-Control-Allow-Credentials"], "true"
            )
            self.assertIn("POST", preflight.headers["Access-Control-Allow-Methods"])
            self.assertIn("OPTIONS", preflight.headers["Access-Control-Allow-Methods"])
            self.assertIn("Content-Type", preflight.headers["Access-Control-Allow-Headers"])

            production = client.options(
                "/api/admin/login",
                headers={
                    "Origin": "https://pyonpyin-agent-frontend.vercel.app",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            self.assertEqual(
                production.headers["Access-Control-Allow-Origin"],
                "https://pyonpyin-agent-frontend.vercel.app",
            )

            with patch.dict(web_app.app.config, {
                "SESSION_COOKIE_SECURE": True,
                "SESSION_COOKIE_SAMESITE": "None",
            }):
                login = client.post(
                    "/api/admin/login",
                    json={"password": "offline-test-password"},
                    headers={"Origin": origin},
                )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.headers["Access-Control-Allow-Origin"], origin)
            self.assertIn("Secure", login.headers["Set-Cookie"])
            self.assertIn("SameSite=None", login.headers["Set-Cookie"])

            blocked = client.options(
                "/api/admin/login",
                headers={
                    "Origin": "https://untrusted.example",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            self.assertNotIn("Access-Control-Allow-Origin", blocked.headers)

    def test_admin_rights_review_requires_explicit_evidence_permissions_and_csrf(self):
        library = {
            "story_id": "pp-rights-review",
            "source_text": "PRIVATE SOURCE",
            "category": "UNCLASSIFIED",
            "license_status": "NEEDS_LICENSE_REVIEW",
            "rights_cleared": "NO",
        }

        class FakeStore:
            writes = []

            def read_records(self, sheet):
                return [library] if sheet == "Story Library" else []

            def upsert_story(self, story):
                library.update(story)
                self.writes.append(dict(story))

        payload = {
            "category": "CHILDREN",
            "category_evidence": "Human-verified publisher age category",
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "human_reviewer": "Rights reviewer",
            "license_evidence": "Verified work-specific permission",
            "rights_jurisdiction": "Myanmar",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
            "permission_for_publication": "NO",
            "permission_for_audio": "NO",
            "permission_for_commercial_use": "NO",
        }
        store = FakeStore()
        with patch.object(web_app, "_store", return_value=store):
            client = web_app.app.test_client()
            self.assertEqual(
                client.put("/api/admin/story/pp-rights-review/rights-review", json=payload).status_code,
                400,
            )
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "rights-csrf"
            missing_csrf = client.put(
                "/api/admin/story/pp-rights-review/rights-review", json=payload
            )
            self.assertEqual(missing_csrf.status_code, 400)
            incomplete = dict(payload, license_evidence="")
            blocked = client.put(
                "/api/admin/story/pp-rights-review/rights-review",
                json=incomplete,
                headers={"X-CSRF-Token": "rights-csrf"},
            )
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(store.writes, [])
            malformed = dict(payload, category=[])
            rejected = client.put(
                "/api/admin/story/pp-rights-review/rights-review",
                json=malformed,
                headers={"X-CSRF-Token": "rights-csrf"},
            )
            self.assertEqual(rejected.status_code, 400)
            saved = client.put(
                "/api/admin/story/pp-rights-review/rights-review",
                json=payload,
                headers={"X-CSRF-Token": "rights-csrf"},
            )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(library["rights_cleared"], "YES")
        self.assertEqual(library["permission_for_publication"], "NO")
        self.assertEqual(library["review_status"], "REVIEWED")
        self.assertEqual(library["source_text"], "PRIVATE SOURCE")
        self.assertEqual(len(store.writes), 1)

    def test_github_dispatch_is_opt_in_policy_checked_and_idempotent_for_queued_story(self):
        story = {
            "story_id": "pp-dispatch",
            "category": "CHILDREN",
            "category_evidence": "Human-reviewed category",
            "rights_mode": "UNKNOWN",
            "broad_theme": "kindness",
            "rights_cleared": "NO",
            "license_status": "NEEDS_LICENSE_REVIEW",
        }
        production = {
            "story_id": "pp-dispatch",
            "draft_mode": "ORIGINAL_THEME",
            "processing_status": "QUEUED",
        }

        class FakeStore:
            def __init__(self):
                self.writes = []
                self.history = []

            def read_records(self, sheet):
                if sheet == "Story Library":
                    return [story]
                if sheet == "Story Production":
                    return [production]
                return []

            def write_production(self, row):
                production.update(row)
                self.writes.append(dict(row))

            def record_processing(self, row):
                self.history.append(dict(row))

        class Response:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        store = FakeStore()
        settings = {
            "PYONPYIN_STORAGE": "sheets",
            "PYONPYIN_GITHUB_DISPATCH_ENABLED": "true",
            "PYONPYIN_GEMINI_AUTOMATION_ENABLED": "true",
            "PYONPYIN_GITHUB_TOKEN": "test-token-not-a-real-credential",
            "PYONPYIN_GITHUB_REPOSITORY": "kyarbites-hub/pyonpyin-agent",
            "PYONPYIN_GITHUB_REF": "main",
        }
        with patch.object(web_app, "_store", return_value=store), patch.dict(
            os.environ, settings
        ), patch("pyonpyin.web_app.urllib.request.urlopen", return_value=Response()) as urlopen:
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "dispatch-csrf"
            disabled = None
            with patch.dict(os.environ, {"PYONPYIN_GITHUB_DISPATCH_ENABLED": "false"}):
                disabled = client.post(
                    "/api/admin/jobs/dispatch",
                    json={"story_id": "pp-dispatch"},
                    headers={"X-CSRF-Token": "dispatch-csrf"},
                )
            self.assertEqual(disabled.status_code, 503)
            self.assertEqual(urlopen.call_count, 0)
            story["category_evidence"] = ""
            blocked = client.post(
                "/api/admin/jobs/dispatch",
                json={"story_id": "pp-dispatch"},
                headers={"X-CSRF-Token": "dispatch-csrf"},
            )
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(urlopen.call_count, 0)
            story["category_evidence"] = "Human-reviewed category"
            accepted = client.post(
                "/api/admin/jobs/dispatch",
                json={"story_id": "pp-dispatch"},
                headers={"X-CSRF-Token": "dispatch-csrf"},
            )
            duplicate = client.post(
                "/api/admin/jobs/dispatch",
                json={"story_id": "pp-dispatch"},
                headers={"X-CSRF-Token": "dispatch-csrf"},
            )

        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(production["processing_status"], "DISPATCHED")
        self.assertEqual(store.history[0]["status"], "DISPATCHED")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"ref": "main", "inputs": {"story_id": "pp-dispatch"}})
        self.assertNotIn("test-token-not-a-real-credential", json.dumps(payload))

    def test_github_dispatch_timeout_is_unknown_and_not_automatically_retried(self):
        story = {
            "story_id": "pp-timeout",
            "category": "CHILDREN",
            "category_evidence": "Human-reviewed category",
            "broad_theme": "friendship",
        }
        production = {
            "story_id": "pp-timeout",
            "draft_mode": "ORIGINAL_THEME",
            "processing_status": "QUEUED",
        }

        class FakeStore:
            def __init__(self):
                self.history = []

            def read_records(self, sheet):
                return [story] if sheet == "Story Library" else [production]

            def write_production(self, row):
                production.update(row)

            def record_processing(self, row):
                self.history.append(dict(row))

        settings = {
            "PYONPYIN_STORAGE": "sheets",
            "PYONPYIN_GITHUB_DISPATCH_ENABLED": "true",
            "PYONPYIN_GEMINI_AUTOMATION_ENABLED": "true",
            "PYONPYIN_GITHUB_TOKEN": "test-token",
            "PYONPYIN_GITHUB_REPOSITORY": "kyarbites-hub/pyonpyin-agent",
        }
        store = FakeStore()
        with patch.object(web_app, "_store", return_value=store), patch.dict(
            os.environ, settings
        ), patch("pyonpyin.web_app.urllib.request.urlopen", side_effect=TimeoutError) as urlopen:
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "timeout-csrf"
            response = client.post(
                "/api/admin/jobs/dispatch",
                json={"story_id": "pp-timeout"},
                headers={"X-CSRF-Token": "timeout-csrf"},
            )
            retry = client.post(
                "/api/admin/jobs/dispatch",
                json={"story_id": "pp-timeout"},
                headers={"X-CSRF-Token": "timeout-csrf"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(production["processing_status"], "DISPATCH_UNKNOWN")
        self.assertEqual(store.history[-1]["status"], "DISPATCH_UNKNOWN")
        self.assertEqual(retry.status_code, 409)
        self.assertEqual(urlopen.call_count, 1)


    def test_admin_draft_editor_validates_episode_continuity_and_resets_content_review(self):
        library = [{
            "story_id": "pp-editor",
            "category": "UNCLASSIFIED",
            "rights_cleared": "NO",
            "license_status": "NEEDS_LICENSE_REVIEW",
        }]
        production = {
            "story_id": "pp-editor",
            "approval_status": "APPROVED",
            "content_review_status": "APPROVED",
            "myanmar_story": "Old story",
        }

        class FakeStore:
            writes = []
            episode_writes = []

            def read_texts(self, _kind):
                return {}

            def read_records(self, sheet):
                if sheet == "Story Library":
                    return library
                if sheet == "Story Production":
                    return [production]
                return []

            def write_production(self, row):
                production.update(row)
                self.writes.append(dict(row))

            def write_episodes(self, story_id, episodes):
                self.episode_writes.append((story_id, episodes))

        store = FakeStore()
        with patch.object(web_app, "_store", return_value=store):
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "editor-csrf"
            missing_csrf = client.put(
                "/api/admin/story/pp-editor/draft",
                json={},
            )
            self.assertEqual(missing_csrf.status_code, 400)
            payload = {
                "myanmar_title": "ခေါင်းစဉ်",
                "myanmar_story": "အစအဆုံး။",
                "episodes": [{
                    "episode_number": 1,
                    "title": "အပိုင်း ၁",
                    "content": "အစအဆုံး။",
                }],
                "quiz": [{"question": "မေးခွန်း", "answer": "အဖြေ"}],
                "reflection": "စဉ်းစားရန်",
                "audio_url": "",
                "audio_status": "NOT_READY",
            }
            invalid = dict(payload)
            invalid["episodes"] = [{
                "episode_number": 1,
                "title": "အပိုင်း ၁",
                "content": "အခြားစာသား",
            }]
            rejected = client.put(
                "/api/admin/story/pp-editor/draft",
                json=invalid,
                headers={"X-CSRF-Token": "editor-csrf"},
            )
            self.assertEqual(rejected.status_code, 400)
            self.assertEqual(store.writes, [])
            unauthorized_audio = dict(payload)
            unauthorized_audio["audio_url"] = "https://example.org/audio.mp3"
            unauthorized_audio["audio_status"] = "READY"
            blocked_audio = client.put(
                "/api/admin/story/pp-editor/draft",
                json=unauthorized_audio,
                headers={"X-CSRF-Token": "editor-csrf"},
            )
            self.assertEqual(blocked_audio.status_code, 409)
            self.assertEqual(store.writes, [])
            saved = client.put(
                "/api/admin/story/pp-editor/draft",
                json=payload,
                headers={"X-CSRF-Token": "editor-csrf"},
            )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(production["processing_status"], "HUMAN_EDITING")
        self.assertEqual(production["content_review_status"], "PENDING")
        self.assertEqual(production["approval_status"], "")
        self.assertEqual(library[0]["rights_cleared"], "NO")
        self.assertEqual(library[0]["license_status"], "NEEDS_LICENSE_REVIEW")
        self.assertEqual(len(store.episode_writes), 1)

    def test_admin_content_approval_is_not_publication_approval(self):
        production = {
            "story_id": "pp-content-review",
            "myanmar_title": "ခေါင်းစဉ်",
            "myanmar_story": "ပုံပြင်။",
            "episodes_json": json.dumps([{
                "episode_number": 1,
                "title": "အပိုင်း ၁",
                "content": "ပုံပြင်။",
                "complete": "YES",
            }], ensure_ascii=False),
            "quiz_json": json.dumps([{"question": "မေးခွန်း", "answer": "အဖြေ"}], ensure_ascii=False),
            "reflection_json": json.dumps("စဉ်းစားရန်", ensure_ascii=False),
            "approval_status": "",
            "content_review_status": "PENDING",
        }

        class FakeStore:
            history = []

            def read_records(self, sheet):
                return [production] if sheet == "Story Production" else []

            def write_production(self, row):
                production.update(row)

            def record_processing(self, row):
                self.history.append(row)

        store = FakeStore()
        with patch.object(web_app, "_store", return_value=store):
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["admin_authenticated"] = True
                session["csrf_token"] = "review-csrf"
            response = client.post(
                "/api/admin/story/pp-content-review/content-review",
                json={"action": "approve"},
                headers={"X-CSRF-Token": "review-csrf"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["content_review_status"], "APPROVED")
        self.assertTrue(response.json["publication_approval_required"])
        self.assertEqual(production["approval_status"], "")
        self.assertEqual(production["processing_status"], "CONTENT_APPROVED")
        self.assertEqual(store.history[0]["status"], "CONTENT_APPROVED")

    def test_public_api_does_not_include_unpublished_drafts(self):
        draft_story = {
            "story_id": "pp-private-draft",
            "category": "UNCLASSIFIED",
            "source_text": "Private source",
        }
        draft = {
            "story_id": "pp-private-draft",
            "myanmar_title": "Private draft",
            "myanmar_story": "Not published",
            "episodes_json": "[]",
            "content_review_status": "PENDING",
            "approval_status": "",
        }
        class FakeStore:
            def read_records(self, sheet):
                if sheet == "Story Library":
                    return [draft_story]
                if sheet == "Story Production":
                    return [draft]
                return []

            def read_texts(self, _text_type):
                return {}

        with patch.object(web_app, "_store", return_value=FakeStore()):
            response = web_app.app.test_client().get("/api/stories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

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
