# PyonPyin AI Agent
# Story discovery and source review workflow for a low-cost Myanmar story pipeline.

import json
import os
import ipaddress
import socket
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit

from pyonpyin.core import (
    candidate_category,
    normalize_url as normalize_source_url,
    safe_story_theme,
    stable_story_id,
)
from pyonpyin.sheets import SheetsStore, retry_transient

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_FILE = BASE_DIR / "data" / "approved_sources.json"
SPREADSHEET_ID = os.environ.get(
    "GOOGLE_SPREADSHEET_ID",
    "",
)


def normalize_url(raw_url):
    """Compatibility wrapper retained for callers of the existing Story Finder."""
    return normalize_source_url(raw_url)


def load_approved_sources(source_file=SOURCES_FILE):
    # ရင်းမြစ်စာရင်းထဲတွင် အတည်ပြုပြီး automation ခွင့်ပြုထားသော source များကိုသာ ဖတ်ယူသည်။
    """Return only approved sources that are allowed to be automated."""
    with source_file.open("r", encoding="utf-8") as file:
        sources = json.load(file)
    if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
        raise ValueError("approved_sources.json must contain a list of source objects.")

    return [
        source for source in sources
        if source.get("approval_status") == "APPROVED"
        and source.get("automation_allowed") is True
    ]


def connect_google_sheets():
    """Return a Sheets API client using the configured OAuth or service account."""
    return SheetsStore().service


class _PlainTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _extract_text(value):
    parser = _PlainTextExtractor()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def verified_public_domain_policy(source):
    policy = source.get("rights_policy", {})
    has_review_details = isinstance(policy, dict) and all(
        isinstance(policy.get(field), str) and policy[field].strip()
        for field in ("evidence", "jurisdiction", "reviewer")
    )
    if not (
        source.get("approval_status") == "APPROVED"
        and source.get("automation_allowed") is True
        and isinstance(policy, dict)
        and policy.get("mode") == "VERIFIED_PUBLIC_DOMAIN"
        and policy.get("all_works_verified") is True
        and has_review_details
        and policy.get("translation_permission") == "YES"
        and policy.get("ai_processing_permission") == "YES"
    ):
        return None
    return policy


def _fetch_verified_text(text_url, feed_host):
    try:
        parsed = urlsplit(text_url)
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.hostname.lower() != feed_host.lower()
    ):
        return ""
    try:
        addresses = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(parsed.hostname, None)
        }
    except (OSError, ValueError):
        return ""
    if not addresses or any(not address.is_global for address in addresses):
        return ""
    try:
        with urllib.request.urlopen(text_url, timeout=20) as response:
            final_url = urlsplit(response.geturl())
            if (
                final_url.scheme.lower() != "https"
                or not final_url.hostname
                or final_url.hostname.lower() != parsed.hostname.lower()
            ):
                return ""
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/plain" not in content_type and "application/octet-stream" not in content_type:
                return ""
            content = response.read(800_001)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return ""
    if len(content) > 800_000:
        return ""
    return _extract_text(content.decode("utf-8-sig", errors="replace"))


def fetch_new_books(feed_url, max_items=None, source_configuration=None, diagnostics=None):
    # HTTPS feed မှ metadata ရယူသည်။ မူရင်းစာသားဖတ်ခြင်းကို verified policy ရှိမှသာ ခွင့်ပြုသည်။
    """Read a source Atom or RSS feed and return discovered book candidates."""
    include_source_text = (
        source_configuration is not None
        and verified_public_domain_policy(source_configuration) is not None
    )
    def failed(reason):
        if diagnostics is not None:
            diagnostics.append(reason)
        return []
    if not feed_url:
        return failed("Missing feed URL")
    try:
        parsed_feed = urlsplit(feed_url)
    except ValueError:
        print("Skipping feed: the configured URL is malformed.")
        return failed("Malformed feed URL")
    if (
        parsed_feed.scheme.lower() != "https"
        or not parsed_feed.hostname
        or parsed_feed.username
        or parsed_feed.password
    ):
        print("Skipping feed: only public HTTPS feed URLs are allowed.")
        return failed("Public HTTPS feed URL required")
    try:
        addresses = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(parsed_feed.hostname, None)
        }
    except (OSError, ValueError) as exc:
        print(f"Unable to resolve approved feed host: {type(exc).__name__}")
        return failed("Feed DNS resolution failed")
    if not addresses or any(not address.is_global for address in addresses):
        print("Skipping feed: feed host does not resolve exclusively to public addresses.")
        return failed("Feed host is not public")

    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "PyonPyinAgent/1.0"},
    )
    xml_data = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                final_url = urlsplit(response.geturl())
                if final_url.scheme.lower() != "https" or not final_url.hostname:
                    print("Skipping feed response: HTTPS redirects are required.")
                    return failed("Non-HTTPS redirect")
                if final_url.hostname.lower() != parsed_feed.hostname.lower():
                    print("Skipping feed response: redirects to a different host are not allowed.")
                    return failed("Cross-host redirect")
                xml_data = response.read(5 * 1024 * 1024 + 1)
                if len(xml_data) > 5 * 1024 * 1024:
                    print("Skipping feed: response exceeds the 5 MiB safety limit.")
                    return failed("Feed exceeds size limit")
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                print(f"Unable to fetch feed; HTTP {exc.code}.")
                exc.close()
                return failed(f"HTTP {exc.code}")
            exc.close()
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if attempt == 2:
                print(f"Unable to fetch feed: {type(exc).__name__}")
                return failed(type(exc).__name__)
        time.sleep(2 ** attempt)
    if xml_data is None:
        return failed("No feed response")

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        print(f"Unable to parse feed {feed_url}: {exc}")
        return failed("Invalid feed XML")

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
    }
    xml_language = root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "")
    rss_language = root.findtext("./channel/language", "")
    feed_language = xml_language or rss_language or "UNKNOWN"

    entries = root.findall(".//atom:entry", namespaces)
    if not entries:
        entries = root.findall(".//item")

    books = []
    for entry in entries:
        title = "Untitled"
        url = ""
        source_identifier = ""
        author = ""
        published_at = ""
        category = ""
        license_url = ""
        item_language = ""
        source_text = ""
        text_url = ""

        if entry.tag.endswith("entry"):
            title_element = entry.find("atom:title", namespaces)
            link_element = None
            for candidate in entry.findall("atom:link", namespaces):
                relation = candidate.attrib.get("rel", "alternate")
                if not candidate.attrib.get("href"):
                    continue
                if relation == "license":
                    license_url = candidate.attrib["href"]
                elif (
                    relation == "alternate"
                    and candidate.attrib.get("type", "").lower() != "text/plain"
                    and link_element is None
                ):
                    link_element = candidate
                if (
                    include_source_text
                    and candidate.attrib.get("type", "").lower() == "text/plain"
                    and relation in {"alternate", "enclosure"}
                ):
                    text_url = candidate.attrib["href"]
            if title_element is not None:
                title = title_element.text or title
            if link_element is not None:
                url = link_element.attrib.get("href", "")
            identifier_element = entry.find("atom:id", namespaces)
            author_element = entry.find("atom:author/atom:name", namespaces)
            published_element = entry.find("atom:published", namespaces)
            category_element = entry.find("atom:category", namespaces)
            content_element = entry.find("atom:content", namespaces)
            if include_source_text and content_element is not None:
                source_text = _extract_text("".join(content_element.itertext()))
            item_language = entry.attrib.get(
                "{http://www.w3.org/XML/1998/namespace}lang", ""
            )
            source_identifier = (
                identifier_element.text if identifier_element is not None else ""
            ) or ""
            author = (author_element.text if author_element is not None else "") or ""
            published_at = (
                published_element.text if published_element is not None else ""
            ) or ""
            category = (
                category_element.attrib.get("term", "")
                if category_element is not None else ""
            )
        else:
            title_element = entry.find("title")
            link_element = entry.find("link")
            if title_element is not None:
                title = title_element.text or title
            if link_element is not None:
                url = link_element.text or link_element.attrib.get("href", "")
            identifier_element = entry.find("guid")
            author_element = entry.find("author")
            published_element = entry.find("pubDate")
            category_element = entry.find("category")
            license_element = entry.find("license")
            content_element = entry.find(
                "{http://purl.org/rss/1.0/modules/content/}encoded"
            )
            enclosure_element = entry.find("enclosure")
            if include_source_text and content_element is not None:
                source_text = _extract_text("".join(content_element.itertext()))
            if (
                include_source_text
                and enclosure_element is not None
                and enclosure_element.attrib.get("type", "").lower() == "text/plain"
            ):
                text_url = enclosure_element.attrib.get("url", "")
            source_identifier = (
                identifier_element.text if identifier_element is not None else ""
            ) or ""
            author = (author_element.text if author_element is not None else "") or ""
            published_at = (
                published_element.text if published_element is not None else ""
            ) or ""
            category = (category_element.text if category_element is not None else "") or ""
            license_url = (license_element.text if license_element is not None else "") or ""

        if not url:
            continue
        if include_source_text and not source_text and text_url:
            source_text = _fetch_verified_text(text_url, parsed_feed.hostname)

        book = {
            "title": title.strip() or "Untitled",
            "url": url.strip(),
            "source_url": url.strip(),
            "source_id": source_identifier.strip(),
            "author": author.strip(),
            "published_at": published_at.strip(),
            "source_category_raw": category.strip(),
            "category": candidate_category(category),
            "source_language": item_language or feed_language,
            "license_url": normalize_url(license_url),
            "license_status": "NEEDS_LICENSE_REVIEW",
            "rights_cleared": "NO",
            "status": "NEEDS_LICENSE_REVIEW",
        }
        if include_source_text and source_text:
            book["source_text"] = source_text
        books.append(book)

        if max_items and len(books) >= max_items:
            break

    return books


def remove_duplicate_books(books):
    """Remove duplicate stories by normalizing their original URLs."""
    unique_books = []
    seen_urls = set()

    for book in books:
        book_url = normalize_url(book.get("url") or book.get("source_url"))
        if not book_url or book_url in seen_urls:
            continue

        seen_urls.add(book_url)
        unique_books.append(book)

    print(f"Books after duplicate check: {len(unique_books)}")
    return unique_books


def cap_candidates_per_category(books, child_limit=5, adult_limit=5, unclassified_limit=5):
    # Run တစ်ကြိမ်တွင် category တစ်မျိုးချင်းစီအတွက် သတ်မှတ်အရေအတွက်ထက် မကျော်အောင် ကန့်သတ်သည်။
    """Keep independent per-cycle caps without guessing unknown age categories."""
    limits = {
        "CHILDREN": child_limit,
        "ADULT": adult_limit,
        "UNCLASSIFIED": unclassified_limit,
    }
    counts = {category: 0 for category in limits}
    selected = []
    for book in books:
        category = candidate_category(book.get("category"))
        if counts[category] >= limits[category]:
            continue
        book["category"] = category
        selected.append(book)
        counts[category] += 1
    print(
        "Discovery candidates: "
        f"children={counts['CHILDREN']}, adults={counts['ADULT']}, "
        f"unclassified={counts['UNCLASSIFIED']}"
    )
    return selected


def create_library_record(book, source):
    # Feed metadata ကို Sheets record အဖြစ်ပြောင်းပြီး မသေချာသော rights ကို ခွင့်ပြုပြီးဟု မသတ်မှတ်ပါ။
    source_name = source.get("source_name", "Unknown")
    source_url = book.get("source_url") or book.get("url", "")
    source_id = book.get("source_id") or normalize_url(source_url)
    category = candidate_category(book.get("category"))
    policy = verified_public_domain_policy(source)
    verified_public_domain = policy is not None
    record = {
        "story_id": stable_story_id(source_name, source_id, source_url),
        "original_title": book.get("title", "Untitled"),
        "author": book.get("author", ""),
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "source_language": book.get("source_language", ""),
        "category": category,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "duplicate_status": "UNIQUE",
        "source_license_rule": source.get("license_rule", "Verify each work"),
        "category_evidence": book.get("category_evidence", ""),
        "license_name": book.get("license_name", ""),
        "license_url": book.get("license_url", ""),
        "license_evidence": (
            str(policy["evidence"]).strip() if verified_public_domain
            else book.get("license_evidence", "")
        ),
        "license_status": "APPROVED" if verified_public_domain else "NEEDS_LICENSE_REVIEW",
        "rights_cleared": "YES" if verified_public_domain else "NO",
        "rights_jurisdiction": (
            str(policy["jurisdiction"]).strip() if verified_public_domain else ""
        ),
        "permission_for_translation": "YES" if verified_public_domain else "NO",
        "permission_for_ai_processing": "YES" if verified_public_domain else "NO",
        "permission_for_publication": "NO",
        "human_reviewer": (
            str(policy["reviewer"]).strip() if verified_public_domain else ""
        ),
        "review_status": (
            "SOURCE_POLICY_VERIFIED" if verified_public_domain else "PENDING_REVIEW"
        ),
        "discovery_error": "",
        "rights_mode": "VERIFIED_PUBLIC_DOMAIN" if verified_public_domain else "UNKNOWN",
        "broad_theme": safe_story_theme(
            category, source.get("broad_theme", book.get("broad_theme", ""))
        ),
        "source_text": book.get("source_text", "") if verified_public_domain else "",
    }
    return record


def queue_automatic_draft(store, record, existing_production):
    """Queue one safe draft per discovered story without overwriting existing work."""
    # Category အထောက်အထားလိုသည်။ မူကြမ်းရှိပြီးသားဆိုလျှင် လူပြင်ထားသောအလုပ်ကို မရေးထပ်ပါ။
    story_id = record.get("story_id", "")
    if not story_id or any(row.get("story_id") == story_id for row in existing_production):
        return False
    category = candidate_category(record.get("category"))
    if (
        category not in {"CHILDREN", "ADULT"}
        or not str(record.get("category_evidence", "") or "").strip()
    ):
        return False

    if record.get("rights_mode") == "VERIFIED_PUBLIC_DOMAIN":
        source_text = record.get("source_text", "")
        source_text_length = len(source_text) if isinstance(source_text, str) else 0
        try:
            source_segments = int(record.get("source_text_segment_count", "0") or 0)
        except (TypeError, ValueError):
            source_segments = 0
        has_bounded_source_text = (
            0 < source_text_length <= 200_000
            or source_text_length == 0 and 0 < source_segments <= 5
        )
        if not (
            record.get("license_status") == "APPROVED"
            and record.get("rights_cleared") == "YES"
            and str(record.get("license_evidence", "") or "").strip()
            and str(record.get("human_reviewer", "") or "").strip()
            and str(record.get("rights_jurisdiction", "") or "").strip()
            and record.get("permission_for_translation") == "YES"
            and record.get("permission_for_ai_processing") == "YES"
            and has_bounded_source_text
        ):
            return False
        draft_mode = "PUBLIC_DOMAIN_RETELLING"
    else:
        if not safe_story_theme(category, record.get("broad_theme", "")):
            return False
        draft_mode = "ORIGINAL_THEME"

    store.write_production({
        "story_id": story_id,
        "draft_mode": draft_mode,
        "processing_status": "QUEUED",
        "content_review_status": "PENDING",
        "approval_status": "",
        "processing_error": "",
        "audio_required": "YES",
    })
    return True


def get_license_approved_books(service):
    """Read the source queue and return rows that are human-approved for licensing."""
    if service is None:
        return []

    try:
        result = retry_transient(lambda: service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="SourceQueue!A2:K",
        ).execute())
    except Exception as exc:  # pragma: no cover - depends on Google API availability.
        raise RuntimeError("Unable to read approved books from Google Sheets.") from exc

    approved_books = []
    for row in result.get("values", []):
        row = row + [""] * max(0, 11 - len(row))
        title = row[0].strip()
        source_url = row[1].strip()
        source_name = row[2].strip()
        license_status = row[3].strip().upper()
        license_evidence = row[5].strip()
        human_reviewer = row[6].strip()
        original_copyright = row[7].strip().upper()
        translation_copyright = row[8].strip().upper()
        thailand_rights_checked = row[9].strip().upper()
        myanmar_translation_rights = row[10].strip().upper()

        if (
            title
            and source_url
            and license_status == "APPROVED"
            and license_evidence
            and human_reviewer
            and original_copyright == "CHECKED"
            and translation_copyright == "CHECKED"
            and thailand_rights_checked == "YES"
            and myanmar_translation_rights == "YES"
        ):
            approved_books.append({
                "title": title,
                "source_url": source_url,
                "source_name": source_name,
                "license_status": license_status,
                "license_evidence": license_evidence,
                "human_reviewer": human_reviewer,
                "original_copyright": original_copyright,
                "translation_copyright": translation_copyright,
                "thailand_rights_checked": thailand_rights_checked,
                "myanmar_translation_rights": myanmar_translation_rights,
            })

    print(f"Human-reviewed, license-approved books: {len(approved_books)}")
    return approved_books


def filter_existing_books(service, books):
    """Filter books already present in the source queue, if Google Sheets is available."""
    if service is None:
        return list(books)

    try:
        result = retry_transient(lambda: service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="SourceQueue!A2:G",
        ).execute())
    except Exception as exc:  # pragma: no cover - depends on API availability.
        raise RuntimeError("Unable to read existing Google Sheets rows.") from exc

    existing_urls = set()
    for row in result.get("values", []):
        if len(row) > 1 and row[1].strip():
            existing_urls.add(normalize_url(row[1]))

    filtered_books = []
    for book in books:
        url = normalize_url(book.get("url") or book.get("source_url"))
        if url and url not in existing_urls:
            filtered_books.append(book)

    print(f"New books not in Google Sheets: {len(filtered_books)}")
    return filtered_books


def existing_source_queue_urls(service):
    try:
        result = retry_transient(lambda: service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="SourceQueue!A2:G",
        ).execute())
    except Exception as exc:  # pragma: no cover - depends on Google API availability.
        raise RuntimeError("Unable to read existing source queue URLs.") from exc
    return {
        normalize_url(row[1])
        for row in result.get("values", [])
        if len(row) > 1 and row[1].strip()
    }


def save_books_to_sheet(service, books, source_name):
    """Append new discovered books to the source queue sheet."""
    if service is None or not books:
        return 0

    try:
        result = retry_transient(lambda: service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="SourceQueue!A2:E",
        ).execute())
        existing_rows = result.get("values", [])
    except Exception as exc:  # pragma: no cover - depends on API availability.
        raise RuntimeError("Unable to read Google Sheets before appending candidates.") from exc

    existing_urls = {
        normalize_url(row[1])
        for row in existing_rows
        if len(row) > 1 and row[1].strip()
    }

    new_rows = []
    for book in books:
        url = normalize_url(book.get("url") or book.get("source_url"))
        if not url or url in existing_urls:
            continue

        new_rows.append([
            book.get("title", "Untitled"),
            url,
            source_name,
            "NEEDS_LICENSE_REVIEW",
            "PENDING_REVIEW",
        ])
        existing_urls.add(url)

    if not new_rows:
        print("New books to save: 0")
        return 0

    retry_transient(lambda: service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="SourceQueue!A:E",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": new_rows},
    ).execute())

    print(f"New books saved: {len(new_rows)}")
    return len(new_rows)


def main(store_override=None, report=None):
    # Discovery သည် စာရင်းသွင်းခြင်းနှင့် queue ထည့်ခြင်းသာလုပ်သည်။ AI generation ကို သီးခြား run ရသည်။
    """Run the story discovery cycle in dry-run mode when Google credentials are absent."""
    from pyonpyin.config import load_environment
    load_environment()
    # တစ်ကြိမ်ရှာတိုင်း အသစ်တွေ့၊ ထပ်နေ၊ အမှားဖြစ်သည့် အရေအတွက်ကို UI အတွက် သိမ်းပေးသည်။
    report = report if report is not None else {}
    report.update(sources=[], found=0, duplicates=0, added=0, drafts_queued=0, deferred=0)
    store = store_override
    if store is not None:
        pass
    elif os.environ.get("PYONPYIN_STORAGE", "").lower() == "sqlite":
        from pyonpyin.storage import get_store
        store = get_store()
    elif (
        os.environ.get("GOOGLE_SPREADSHEET_ID")
        and (
            os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
            or os.environ.get("GOOGLE_TOKEN_JSON")
            or os.environ.get("GOOGLE_TOKEN_FILE")
        )
    ):
        print("Connecting to Google Sheets...")
        store = SheetsStore()
        store.ensure_schema()
    else:
        print("Proceeding with dry-run mode; no Google Sheets updates will be written.")

    approved_sources = load_approved_sources()
    if not approved_sources:
        print("No approved sources are configured for automation.")
        return 0

    library_records = list(store.read_records("Story Library")) if store is not None else []
    known_ids = {row.get("story_id", "") for row in library_records}
    known_urls = {
        normalize_url(row.get("source_url", ""))
        for row in library_records
        if row.get("source_url")
    }
    legacy_urls = existing_source_queue_urls(store.service) if store is not None and hasattr(store, "service") else set()
    discovered = []
    for source in approved_sources:
        feed_url = source.get("feed_url")
        if not feed_url:
            print(f"Skipping source without feed_url: {source.get('source_name')}")
            continue

        print(f"\nChecking source: {source.get('source_name')}")
        diagnostics = []
        books = fetch_new_books(
            feed_url,
            max_items=15 if verified_public_domain_policy(source) else None,
            source_configuration=source,
            diagnostics=diagnostics,
        )
        report["sources"].append({"name": source.get("source_name", ""), "found": len(books),
                                  "errors": diagnostics})
        report["found"] += len(books)
        print(f"Books found: {len(books)}")
        for book in remove_duplicate_books(books):
            raw_category = book.pop("source_category_raw", "")
            if source.get("source_language"):
                book["source_language"] = source["source_language"]
            mapping = source.get("category_mapping", {})
            if not isinstance(mapping, dict):
                raise ValueError(
                    f"category_mapping for {source.get('source_name')} must be an object."
                )
            category_mapping = {
                str(key).casefold(): candidate_category(value)
                for key, value in mapping.items()
            }
            mapped_category = category_mapping.get(raw_category.casefold())
            feed_category = candidate_category(raw_category)
            configured_category = source.get("default_category")
            if mapped_category:
                book["category"] = mapped_category
                book["category_evidence"] = f"Configured feed category mapping: {raw_category}"
            elif feed_category in {"CHILDREN", "ADULT"}:
                book["category"] = feed_category
                book["category_evidence"] = f"Explicit feed audience category: {raw_category}"
            elif configured_category in {"CHILDREN", "ADULT"}:
                book["category"] = configured_category
                book["category_evidence"] = "Human-approved source default category"
            else:
                book["category"] = "UNCLASSIFIED"
                book["category_evidence"] = (
                    f"Unmapped feed category: {raw_category}" if raw_category
                    else "No source age-category evidence"
                )
            book["broad_theme"] = safe_story_theme(
                book["category"],
                raw_category or source.get("broad_theme", ""),
            )
            book["_source"] = source
            discovered.append(book)

    fresh = []
    seen_ids = set()
    seen_urls = set()
    legacy_backfills = {}
    for book in discovered:
        source = book["_source"]
        record = create_library_record(book, source)
        url = normalize_url(record["source_url"])
        if record["story_id"] in seen_ids or url in seen_urls:
            report["duplicates"] += 1
            continue
        seen_ids.add(record["story_id"])
        seen_urls.add(url)
        if record["story_id"] in known_ids or url in known_urls:
            report["duplicates"] += 1
            if (
                store is not None
                and record["story_id"] in known_ids
                and url not in legacy_urls
            ):
                legacy_backfills.setdefault(source.get("source_name", "Unknown"), []).append(book)
            continue
        fresh.append((book, source, record, url in legacy_urls))

    candidates = cap_candidates_per_category(
        [record for _, _, record, _ in fresh]
    )
    candidate_ids = {record["story_id"] for record in candidates}
    new_candidates = [item for item in fresh if item[2]["story_id"] in candidate_ids]
    report["deferred"] = len(fresh) - len(new_candidates)

    print(f"New candidates selected: {len(new_candidates)}")
    existing_production = (
        list(store.read_records("Story Production")) if store is not None else []
    )
    legacy_additions = dict(legacy_backfills)
    library_saved = 0
    drafts_queued = 0
    for book, source, record, already_in_legacy in new_candidates:
        if store is None:
            print(
                f"- [{record['category']}] {record['original_title']} "
                f"({record['story_id']}) -> {record['source_url']}"
            )
            continue
        store.upsert_story(record)
        library_saved += 1
        if queue_automatic_draft(store, record, existing_production):
            existing_production.append({
                "story_id": record["story_id"],
                "processing_status": "QUEUED",
            })
            drafts_queued += 1
        if not already_in_legacy:
            legacy_additions.setdefault(source.get("source_name", "Unknown"), []).append(book)

    print(f"Story Library candidates saved: {library_saved}")
    if store is not None:
        for existing_record in library_records:
            if queue_automatic_draft(store, existing_record, existing_production):
                existing_production.append({
                    "story_id": existing_record.get("story_id", ""),
                    "processing_status": "QUEUED",
                })
                drafts_queued += 1
    print(f"Automatic safe drafts queued: {drafts_queued}")
    report.update(added=library_saved, drafts_queued=drafts_queued)
    if report["sources"] and all(item["errors"] for item in report["sources"]):
        return 1
    if store is not None and hasattr(store, "service"):
        legacy_saved = 0
        for source_name, books in legacy_additions.items():
            legacy_saved += save_books_to_sheet(store.service, books, source_name)
        print(f"Legacy SourceQueue entries saved: {legacy_saved}")

    print("\nStory Finder completed successfully.")
    print("Unknown-rights text is never forwarded to Gemini.")
    print("Unclassified feed entries are saved but not queued.")
    print("Gemini generation runs separately and is opt-in.")
    print("Auto publishing remains disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
