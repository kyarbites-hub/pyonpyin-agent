"""Shared story snapshots and private audio storage for the API and worker."""

import json
import os
import uuid
from pathlib import Path

from pyonpyin.audio import validate_audio
from pyonpyin.core import publication_blockers


def story_snapshot(store, story_id):
    library = next((r for r in store.read_records("Story Library") if r.get("story_id") == story_id), None)
    production = next((r for r in store.read_records("Story Production") if r.get("story_id") == story_id), None)
    if library is None or production is None:
        raise LookupError("Story and production draft must exist.")
    production = dict(production)
    if not production.get("myanmar_story"):
        production["myanmar_story"] = store.read_texts("MYANMAR").get(story_id, "")
    raw = production.get("episodes_json") or store.read_texts("EPISODES").get(story_id, "")
    episodes = json.loads(raw or "[]")
    if not isinstance(episodes, list):
        raise ValueError("Saved episode data must be a list.")
    return library, production, episodes


def publicly_visible(store, library, production, episodes):
    story_id = library["story_id"]
    published = any(r.get("story_id") == story_id and r.get("publication_status") == "PUBLISHED"
                    for r in store.read_records("Publishing History"))
    return published and not publication_blockers(
        {**library, **production}, episodes, production.get("audio_required") == "YES")


def audio_directory():
    return Path(os.environ.get("AUDIO_OUTPUT_DIR", "data/runtime/audio")).resolve()


def save_audio(data, suffix):
    validate_audio(data, suffix)
    directory = audio_directory()
    directory.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + suffix
    path = directory / filename
    # Filename ကို server ကထုတ်ပြီး user ပေးသည့် path ကို မသုံးပါ။
    with path.open("xb") as output:
        output.write(data)
    return "/media/audio/" + filename
