"""Google Sheets persistence with additive, non-destructive schema setup."""

import os
import json
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from pyonpyin.core import utc_now


SHEETS = {
    "Story Library": [
        "story_id", "original_title", "author", "source_id", "source_name",
        "source_url", "source_language", "category", "source_text", "source_published_at",
        "discovered_at",
        "duplicate_status", "source_license_rule", "category_evidence", "license_name",
        "license_url", "license_evidence", "license_status", "rights_cleared",
        "rights_jurisdiction", "permission_for_translation",
        "permission_for_ai_processing", "permission_for_publication",
        "permission_for_audio", "permission_for_commercial_use",
        "source_text_segment_count", "human_reviewer", "review_status", "discovery_error",
        "rights_mode", "broad_theme",
    ],
    "Story Text": [
        "text_key", "story_id", "text_type", "segment_number", "content", "active",
    ],
    "Story Production": [
        "story_id", "myanmar_title", "myanmar_story", "episodes_json", "quiz_json",
        "reflection_json", "model_name", "prompt_version", "content_review_status",
        "license_review_status", "approval_status", "audio_url", "audio_status",
        "audio_required", "processing_status", "processing_error", "updated_at",
        "myanmar_story_segment_count", "episodes_json_segment_count",
        "draft_mode",
    ],
    "Story Episodes": [
        "episode_key", "story_id", "episode_number", "title", "content", "complete",
        "audio_url", "audio_status", "review_status",
    ],
    "Processing History": [
        "processing_id", "story_id", "status", "started_at", "completed_at",
        "model_name", "retry_count", "error_details",
    ],
    "Publishing History": [
        "publication_id", "story_id", "published_title", "website_url",
        "published_at", "episode_count", "publication_status", "retry_count",
        "error_details", "approved_by",
    ],
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_CELL_SAFE_LIMIT = 40_000


class SheetsStore:
    def __init__(self, service=None, spreadsheet_id=None):
        self.spreadsheet_id = spreadsheet_id or os.environ.get("GOOGLE_SPREADSHEET_ID", "")
        if not self.spreadsheet_id:
            raise RuntimeError("Set GOOGLE_SPREADSHEET_ID before using Google Sheets.")
        self.service = service or self._connect()

    @staticmethod
    def _connect():
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if service_account_json:
            try:
                info = json.loads(service_account_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must contain valid JSON.") from exc
            from google.oauth2.service_account import Credentials as ServiceAccountCredentials

            credentials = ServiceAccountCredentials.from_service_account_info(
                info, scopes=SCOPES
            )
            return build("sheets", "v4", credentials=credentials, cache_discovery=False)

        token = os.environ.get("GOOGLE_TOKEN_JSON")
        token_file = os.environ.get("GOOGLE_TOKEN_FILE")
        if token:
            try:
                token_data = json.loads(token)
            except json.JSONDecodeError as exc:
                raise RuntimeError("GOOGLE_TOKEN_JSON must contain valid JSON.") from exc
        elif token_file:
            try:
                token_data = json.loads(Path(token_file).read_text(encoding="utf-8"))
            except OSError as exc:
                raise RuntimeError("Unable to read the configured GOOGLE_TOKEN_FILE.") from exc
            except json.JSONDecodeError as exc:
                raise RuntimeError("GOOGLE_TOKEN_FILE must contain valid JSON.") from exc
        else:
            raise RuntimeError("Set GOOGLE_TOKEN_JSON or GOOGLE_TOKEN_FILE before using Google Sheets.")
        credentials = Credentials.from_authorized_user_info(token_data, scopes=SCOPES)
        return build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def _values(self):
        return self.service.spreadsheets().values()

    @staticmethod
    def _execute(request):
        return retry_transient(request.execute, attempts=3)

    def ensure_schema(self):
        spreadsheet = self._execute(self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            fields="sheets.properties(sheetId,title)",
        ))
        existing = {
            sheet["properties"]["title"]: sheet["properties"]["sheetId"]
            for sheet in spreadsheet.get("sheets", [])
        }
        requests = [
            {"addSheet": {"properties": {"title": title}}}
            for title in SHEETS if title not in existing
        ]
        if requests:
            response = self._execute(self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"requests": requests}
            ))
            for item in response.get("replies", []):
                properties = item.get("addSheet", {}).get("properties", {})
                if properties.get("title") is not None:
                    existing[properties["title"]] = properties["sheetId"]

        for title, required in SHEETS.items():
            header_result = self._execute(self._values().get(
                spreadsheetId=self.spreadsheet_id, range=f"'{title}'!1:1"
            ))
            current = (header_result.get("values") or [[]])[0]
            if not current:
                self._execute(self._values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{title}'!A1",
                    valueInputOption="RAW",
                    body={"values": [required]},
                ))
                continue
            missing = [header for header in required if header not in current]
            if missing:
                occupied = self._execute(self._values().get(
                    spreadsheetId=self.spreadsheet_id, range=f"'{title}'!A:ZZ"
                )).get("values", [])
                last_column = max((len(row) for row in occupied), default=len(current))
                start_column = max(len(current), last_column) + 1
                self._execute(self._values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{title}'!{_column_name(start_column)}1",
                    valueInputOption="RAW",
                    body={"values": [missing]},
                ))

    def read_records(self, sheet_name):
        self._check_sheet(sheet_name)
        result = self._execute(self._values().get(
            spreadsheetId=self.spreadsheet_id, range=f"'{sheet_name}'!A:ZZ"
        ))
        rows = result.get("values", [])
        if not rows:
            return []
        headers = rows[0]
        return [
            {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
            for row in rows[1:]
            if any(str(value).strip() for value in row)
        ]

    def upsert(self, sheet_name, key_column, record):
        """Update a matching stable key or append without replacing user data."""
        return self.upsert_many(sheet_name, key_column, [record])[0]

    def upsert_many(self, sheet_name, key_column, records):
        self._check_sheet(sheet_name)
        records_by_key = {}
        for record in records:
            key = record.get(key_column)
            if not key:
                raise ValueError(f"{key_column} is required for an idempotent Sheets update.")
            key = str(key)
            records_by_key.setdefault(key, {}).update(record)
        if not records_by_key:
            return []
        records = list(records_by_key.values())
        result = self._execute(self._values().get(
            spreadsheetId=self.spreadsheet_id, range=f"'{sheet_name}'!A:ZZ"
        ))
        rows = result.get("values", [])
        if not rows:
            raise RuntimeError(f"'{sheet_name}' has no header row; initialize its schema first.")
        headers = rows[0]
        if key_column not in headers:
            raise RuntimeError(f"'{sheet_name}' is missing required column {key_column}.")
        key_index = headers.index(key_column)
        row_indexes = {
            row[key_index]: (index + 2, row)
            for index, row in enumerate(rows[1:])
            if len(row) > key_index and row[key_index]
        }
        updates = {}
        appends = []
        result_rows = []
        next_row = len(rows) + 1
        for record in records:
            key = str(record[key_column])
            existing = row_indexes.get(key)
            row_number, existing_row = existing if existing is not None else (next_row, None)
            if existing is None:
                next_row += 1
            values = [
                record[header] if header in record else (
                    existing_row[index] if existing_row is not None and index < len(existing_row) else ""
                )
                for index, header in enumerate(headers)
            ]
            if existing is None:
                appends.append(values)
                row_indexes[key] = (row_number, values)
            else:
                updates[row_number] = values
                row_indexes[key] = (row_number, values)
            result_rows.append(row_number)
        if updates:
            self._execute(self._values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": [
                        {
                            "range": f"'{sheet_name}'!A{row_number}",
                            "values": [values],
                        }
                        for row_number, values in updates.items()
                    ],
                },
            ))
        if appends:
            self._execute(self._values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{sheet_name}'!A:ZZ",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": appends},
            ))
        return result_rows

    def upsert_story(self, story):
        library = dict(story)
        library.setdefault("discovered_at", utc_now())
        library.setdefault("duplicate_status", "UNIQUE")
        text = library.get("source_text", "")
        if text:
            segment_count = self.write_text(library["story_id"], "SOURCE", text)
            library["source_text_segment_count"] = str(segment_count)
            if len(text) > SHEET_CELL_SAFE_LIMIT:
                library["source_text"] = ""
        self.upsert("Story Library", "story_id", library)

    def write_production(self, story):
        story = dict(story)
        story["updated_at"] = utc_now()
        for field, text_type, count_field in (
            ("myanmar_story", "MYANMAR", "myanmar_story_segment_count"),
            ("episodes_json", "EPISODES", "episodes_json_segment_count"),
        ):
            text = story.get(field, "")
            if text:
                segment_count = self.write_text(story["story_id"], text_type, text)
                story[count_field] = str(segment_count)
                if len(text) > SHEET_CELL_SAFE_LIMIT:
                    story[field] = ""
        self.upsert("Story Production", "story_id", story)

    def write_text(self, story_id, text_type, text):
        if text_type not in {"SOURCE", "MYANMAR", "EPISODES"}:
            raise ValueError("text_type must be SOURCE, MYANMAR, or EPISODES.")
        previous = [
            row for row in self.read_records("Story Text")
            if row.get("story_id") == story_id and row.get("text_type") == text_type
            and row.get("active", "").upper() == "YES"
        ]
        if len(text) <= SHEET_CELL_SAFE_LIMIT:
            for row in previous:
                row["active"] = "NO"
            self.upsert_many("Story Text", "text_key", previous)
            return 0
        segments = [
            text[index:index + SHEET_CELL_SAFE_LIMIT]
            for index in range(0, len(text), SHEET_CELL_SAFE_LIMIT)
        ]
        segment_records = [{
                "text_key": f"{story_id}:{text_type}:{number}",
                "story_id": story_id,
                "text_type": text_type,
                "segment_number": str(number),
                "content": content,
                "active": "YES",
            }
            for number, content in enumerate(segments, 1)
        ]
        self.upsert_many("Story Text", "text_key", segment_records)
        stale = []
        for row in previous:
            if int(row.get("segment_number", 0)) > len(segments):
                row["active"] = "NO"
                stale.append(row)
        self.upsert_many("Story Text", "text_key", stale)
        return len(segments)

    def read_texts(self, text_type):
        if text_type not in {"SOURCE", "MYANMAR", "EPISODES"}:
            raise ValueError("text_type must be SOURCE, MYANMAR, or EPISODES.")
        grouped = {}
        for row in self.read_records("Story Text"):
            if row.get("text_type") != text_type or row.get("active", "").upper() != "YES":
                continue
            grouped.setdefault(row.get("story_id", ""), []).append(row)
        return {
            story_id: "".join(
                row.get("content", "")
                for row in sorted(records, key=lambda item: int(item["segment_number"]))
            )
            for story_id, records in grouped.items()
        }

    def write_episodes(self, story_id, episodes):
        for number, episode in enumerate(episodes, 1):
            if not isinstance(episode, dict) or not isinstance(episode.get("content", ""), str):
                raise ValueError(f"Episode {number} must be a text object.")
            if len(episode.get("content", "")) > SHEET_CELL_SAFE_LIMIT:
                raise ValueError(
                    f"Episode {number} exceeds the safe Google Sheets cell limit."
                )
        existing = {
            int(row.get("episode_number", 0)): row
            for row in self.read_records("Story Episodes")
            if row.get("story_id") == story_id
        }
        records = []
        for number, episode in enumerate(episodes, 1):
            previous = existing.get(number, {})
            changed_text = previous.get("content", "") != episode.get("content", "")
            records.append({
                **episode,
                "story_id": story_id,
                "episode_key": f"{story_id}:{number}",
                "episode_number": str(number),
                "complete": "YES",
                "audio_url": (
                    "" if changed_text
                    else episode.get("audio_url", previous.get("audio_url", ""))
                ),
                "audio_status": (
                    "NOT_READY" if changed_text
                    else episode.get("audio_status", previous.get("audio_status", "NOT_READY"))
                ),
            })
        self.upsert_many("Story Episodes", "episode_key", records)
        stale = []
        for number, record in existing.items():
            if number > len(episodes):
                record["complete"] = "NO"
                stale.append(record)
        self.upsert_many("Story Episodes", "episode_key", stale)

    def record_publication(self, record):
        self.upsert("Publishing History", "publication_id", record)

    def record_processing(self, record):
        self.upsert("Processing History", "processing_id", record)

    def _check_sheet(self, sheet_name):
        if sheet_name not in SHEETS:
            raise ValueError(f"Unsupported sheet: {sheet_name}")

def _column_name(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def retry_transient(operation, attempts=3, base_delay=1):
    """Retry only transient Google API status codes, with a strict attempt bound."""
    from googleapiclient.errors import HttpError

    for attempt in range(attempts):
        try:
            return operation()
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise
            time.sleep(base_delay * (2 ** attempt))
