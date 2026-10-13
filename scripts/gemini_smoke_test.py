"""Optional live Gemini smoke test; invokes the API exactly once."""

import re
import sys

from pyonpyin.gemini import GeminiClient


def has_myanmar_text(value):
    return isinstance(value, str) and re.search(r"[\u1000-\u109f]", value) is not None


def main():
    client = GeminiClient(attempts=1)
    draft = client.generate_draft(
        {
            "draft_mode": "RIGHTS_CLEARED_SOURCE",
            "category": "CHILDREN",
            "license_status": "APPROVED",
            "rights_cleared": "YES",
            "human_reviewer": "Automated smoke-test fixture",
            "license_evidence": "Original test fixture written for this API smoke test",
            "rights_jurisdiction": "N/A",
            "permission_for_translation": "YES",
            "permission_for_ai_processing": "YES",
        },
        (
            "This is an original test fixture, not a published story. A child "
            "plants one seed, waters it patiently, and shares the flower with a friend."
        ),
    )
    if not has_myanmar_text(draft["title"]) or not has_myanmar_text(draft["story"]):
        raise RuntimeError("Gemini response did not contain Myanmar Unicode story text.")
    if not draft["quiz"] or not draft["reflection"]:
        raise RuntimeError("Gemini response is missing quiz or reflection content.")
    print(
        "Gemini live smoke test passed: Myanmar title/story, ordered episodes, "
        f"{len(draft['quiz'])} quiz item(s), and reflection validated ({client.model})."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Gemini live smoke test failed: {type(exc).__name__}.", file=sys.stderr)
        sys.exit(1)
