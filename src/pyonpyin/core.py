"""Shared story identity, rights gates, and safe workflow primitives."""

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


CATEGORIES = {"CHILDREN", "ADULT", "UNCLASSIFIED"}
SAFE_THEMES = {
    "adventure",
    "belonging",
    "cooperation",
    "curiosity",
    "courage",
    "friendship",
    "kindness",
    "nature",
    "perseverance",
    "resilience",
}
DEFAULT_THEMES = {
    "CHILDREN": "kindness",
    "ADULT": "resilience",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_url(raw_url):
    if not raw_url:
        return ""
    try:
        parsed = urlsplit(raw_url.strip())
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        return ""
    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        parsed.query,
        "",
    ))


def stable_story_id(source_name, source_identifier, source_url):
    """A deterministic identity across discovery reruns and title changes."""
    stable_key = source_identifier or normalize_url(source_url)
    if not source_name or not stable_key:
        raise ValueError("A source name and source identifier or URL are required.")
    digest = hashlib.sha256(
        f"{source_name.strip().lower()}\0{stable_key.strip()}".encode("utf-8")
    ).hexdigest()[:24]
    return f"pp-{digest}"


def candidate_category(raw_category):
    value = (raw_category or "").strip().upper()
    aliases = {
        "CHILD": "CHILDREN",
        "CHILDREN'S": "CHILDREN",
        "CHILDRENS": "CHILDREN",
        "YOUNG ADULT": "CHILDREN",
        "ADULTS": "ADULT",
    }
    value = aliases.get(value, value)
    return value if value in CATEGORIES else "UNCLASSIFIED"


def safe_story_theme(category, requested_theme=""):
    """Return an allowlisted general idea, never arbitrary feed text."""
    audience = (category or "").strip().upper()
    if audience not in {"CHILDREN", "ADULT"}:
        return ""
    requested = (requested_theme or "").strip().casefold()
    if requested in SAFE_THEMES:
        return requested
    return DEFAULT_THEMES[audience]


def eligible_candidate(story):
    """Only exact human-entered clearance permits AI processing."""
    return (
        story.get("category", "").strip().upper() in {"CHILDREN", "ADULT"}
        and story.get("license_status", "").strip().upper() == "APPROVED"
        and story.get("rights_cleared", "").strip().upper() == "YES"
        and bool(story.get("human_reviewer", "").strip())
        and bool(story.get("license_evidence", "").strip())
        and bool(story.get("rights_jurisdiction", "").strip())
        and story.get("permission_for_translation", "").strip().upper() == "YES"
        and story.get("permission_for_ai_processing", "").strip().upper() == "YES"
    )


def valid_audio_reference(value):
    if not isinstance(value, str) or "\\" in value:
        return False
    candidate = value.strip()
    if candidate.startswith("/") and not candidate.startswith("//"):
        return True
    return bool(normalize_url(candidate))


def publication_blockers(story, episodes, require_audio=False):
    blockers = []
    if story.get("category", "").strip().upper() not in {"CHILDREN", "ADULT"}:
        blockers.append("Story category must be explicitly reviewed as CHILDREN or ADULT.")
    if not eligible_candidate(story):
        blockers.append("Rights are not cleared with evidence, reviewer, and jurisdiction.")
    if story.get("permission_for_publication", "").strip().upper() != "YES":
        blockers.append("Permission for public distribution is not explicitly confirmed.")
    audio_records = [story, *(episodes if isinstance(episodes, list) else [])]
    ready_audio = [
        item for item in audio_records
        if isinstance(item, dict)
        and item.get("audio_status", "").strip().upper() == "READY"
    ]
    if ready_audio and story.get("permission_for_audio", "").strip().upper() != "YES":
        blockers.append("Audio narration lacks explicit rights permission.")
    if any(
        not valid_audio_reference(item.get("audio_url", ""))
        for item in ready_audio
    ):
        blockers.append("A ready audio asset has an invalid URL.")
    if story.get("content_review_status", "").strip().upper() != "APPROVED":
        blockers.append("Complete Myanmar story has not passed human review.")
    if story.get("approval_status", "").strip().upper() != "APPROVED":
        blockers.append("Explicit human publication approval is missing.")
    if not episodes:
        blockers.append("No complete episodes are available.")
    else:
        if any(not isinstance(item, dict) for item in episodes):
            blockers.append("Episode records are malformed.")
            ordered = []
        else:
            try:
                ordered = sorted(episodes, key=lambda item: int(item.get("episode_number", 0)))
                numbers = [int(item.get("episode_number", 0)) for item in ordered]
                if numbers != list(range(1, len(ordered) + 1)):
                    blockers.append("Episode sequence is incomplete or out of order.")
            except (TypeError, ValueError):
                ordered = []
                blockers.append("Episode numbers must be valid integers.")
        if any(not isinstance(item.get("content"), str) or not item["content"].strip() for item in ordered):
            blockers.append("One or more episodes are empty.")
        if any(str(item.get("complete", "YES")).strip().upper() != "YES" for item in ordered):
            blockers.append("One or more episodes are marked incomplete.")
        if story.get("myanmar_story", "").strip():
            complete_text = " ".join(story["myanmar_story"].split())
            episode_text = " ".join(
                "".join(
                    item.get("content", "")
                    for item in ordered
                    if isinstance(item.get("content"), str)
                ).split()
            )
            if episode_text != complete_text:
                blockers.append("Episodes do not exactly partition the complete Myanmar story.")
    if require_audio and (
        not story.get("audio_url", "").strip()
        or story.get("audio_status", "").strip().upper() != "READY"
        or story.get("permission_for_audio", "").strip().upper() != "YES"
        or not valid_audio_reference(story.get("audio_url", ""))
    ):
        blockers.append("Required narration permission or audio asset is not ready.")
    if not story.get("myanmar_title", "").strip() or not story.get("myanmar_story", "").strip():
        blockers.append("Complete Myanmar title and story text are required.")
    return blockers


def parse_json_object(text):
    """Parse either a JSON response or JSON fenced by a model."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("The model response must be a JSON object.")
    return value
