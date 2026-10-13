"""Gemini REST adapter with bounded retries and strict draft validation."""

import json
import os
import time
import urllib.error
import urllib.request

from pyonpyin.core import eligible_candidate, parse_json_object, safe_story_theme

MAX_STORY_TEXT_CHARS = 200_000
MAX_EPISODE_TEXT_CHARS = 40_000


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key=None, model=None, timeout=40, attempts=2):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
        self.timeout = timeout
        self.attempts = attempts
        self.retry_count = 0
        if not self.api_key:
            raise RuntimeError("Set GEMINI_API_KEY before generating story drafts.")

    def generate_draft(self, story, source_text):
        mode = story.get("draft_mode", "RIGHTS_CLEARED_SOURCE").strip().upper()
        category = story.get("category", "").strip().upper()
        if category not in {"CHILDREN", "ADULT"}:
            raise PermissionError("An explicit CHILDREN or ADULT category is required.")

        if mode == "ORIGINAL_THEME":
            theme = safe_story_theme(category, story.get("broad_theme", ""))
            if not theme:
                raise PermissionError("A safe, allowlisted broad theme is required.")
            if source_text:
                raise PermissionError(
                    "Source text cannot be sent when generating an original theme-based story."
                )
            prompt = (
                "Create a completely original Myanmar Unicode story inspired only by "
                "the following broad, non-exclusive idea. Do not use, imitate, retell, "
                "or refer to any existing book, story, title, author, characters, scenes, "
                "dialogue, plot sequence, or source text. Invent new characters, setting, "
                "events, dialogue, and wording. Make the result suitable for the stated "
                "audience. Return only JSON with keys title, story, episodes, quiz, "
                "reflection. Episodes must be an ordered array of objects with "
                "episode_number, title, content. Episode contents must partition the "
                "complete story exactly and in order. Quiz must contain question/answer "
                "objects and reflection a short question. Keep the complete story "
                "concise enough to fit within about 6,000 output tokens.\n"
                f"Audience: {category}. Broad idea: {theme}."
            )
        elif mode in {"PUBLIC_DOMAIN_RETELLING", "RIGHTS_CLEARED_SOURCE"}:
            if not eligible_candidate(story):
                raise PermissionError(
                    "Gemini processing is blocked until rights are explicitly cleared."
                )
            if not isinstance(source_text, str) or not source_text.strip():
                raise ValueError("Rights-cleared source story text is required.")
            if len(source_text) > MAX_STORY_TEXT_CHARS:
                raise ValueError("Source story exceeds the configured 200,000-character limit.")
            instruction = (
                "Create a genuinely original Myanmar retelling, not a translation or "
                "close paraphrase. Use new wording, expressive storytelling, and original "
                "dialogue while retaining the high-level premise and essential meaning. "
                "Do not reproduce source phrasing."
                if mode == "PUBLIC_DOMAIN_RETELLING"
                else
                "Adapt the provided rights-cleared source into natural Myanmar Unicode. "
                "Preserve plot, meaning and important details; do not invent facts."
            )
            prompt = (
                f"{instruction} Use age-appropriate language for {category}. "
                "Return only JSON with keys title, story, episodes, quiz, reflection. "
                "Episodes must be an ordered array of objects with episode_number, title, "
                "content. Episode contents must partition the complete story exactly and "
                "in order. Quiz must contain question/answer objects and reflection a "
                "short question. "
                f"Category: {category}.\n\nRights-cleared source story:\n{source_text}"
            )
        else:
            raise ValueError(f"Unsupported draft mode: {mode}")

        result = self._request(prompt)
        required = {"title", "story", "episodes", "quiz", "reflection"}
        if not required.issubset(result):
            raise GeminiError("Gemini response is missing required story fields.")
        if (
            not isinstance(result["title"], str)
            or len(result["title"]) > 500
            or not isinstance(result["story"], str)
        ):
            raise GeminiError("Gemini title and story must be text.")
        if not isinstance(result["episodes"], list) or not result["episodes"]:
            raise GeminiError("Gemini must return at least one episode.")
        if len(result["episodes"]) > 100:
            raise GeminiError("Gemini returned more than 100 episodes.")
        full_text = " ".join(result["story"].split())
        segments = []
        for number, episode in enumerate(result["episodes"], 1):
            if (
                not isinstance(episode, dict)
                or type(episode.get("episode_number")) is not int
                or episode["episode_number"] != number
                or not isinstance(episode.get("content"), str)
                or not episode["content"].strip()
                or len(episode["content"]) > MAX_EPISODE_TEXT_CHARS
                or not isinstance(episode.get("title"), str)
                or not episode["title"].strip()
            ):
                raise GeminiError("Gemini returned an invalid or incomplete episode sequence.")
            segments.append(episode["content"])
        if " ".join("".join(segments).split()) != full_text:
            raise GeminiError("Episode text does not exactly partition the complete draft.")
        if sum(map(len, segments)) > MAX_STORY_TEXT_CHARS:
            raise GeminiError("Gemini story exceeds the configured 200,000-character limit.")
        if not isinstance(result["quiz"], list) or not result["quiz"] or len(result["quiz"]) > 20:
            raise GeminiError("Gemini must return at least one quiz question.")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("question"), str)
            or not item["question"].strip()
            or len(item["question"]) > 1_000
            or not isinstance(item.get("answer"), str)
            or not item["answer"].strip()
            or len(item["answer"]) > 1_000
            for item in result["quiz"]
        ):
            raise GeminiError("Each quiz item must contain a question and answer.")
        if (
            not isinstance(result["reflection"], (str, list))
            or isinstance(result["reflection"], list) and len(result["reflection"]) > 10
            or isinstance(result["reflection"], str) and len(result["reflection"]) > 2_000
            or isinstance(result["reflection"], list)
            and any(not isinstance(item, str) or len(item) > 2_000 for item in result["reflection"])
        ):
            raise GeminiError("Gemini returned an invalid reflection value.")
        if not result["reflection"]:
            raise GeminiError("Gemini returned an empty reflection.")
        return result

    def _request(self, prompt):
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 8192,
            },
        }).encode("utf-8")
        for attempt in range(self.attempts):
            request = urllib.request.Request(
                endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                return parse_json_object(text)
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 == self.attempts:
                    raise GeminiError(f"Gemini request failed with HTTP {exc.code}.") from exc
                self.retry_count += 1
                time.sleep(min(2 ** attempt, 8))
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt + 1 == self.attempts:
                    raise GeminiError("Gemini request failed after bounded retries.") from exc
                self.retry_count += 1
                time.sleep(min(2 ** attempt, 8))
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise GeminiError("Gemini returned an invalid response shape.") from exc
        raise GeminiError("Gemini request exhausted its retry limit.")
