"""Local setup, secret-free diagnostics, and consistent database backups."""

import argparse
import json
import os
import secrets
from pathlib import Path

from pyonpyin.config import load_environment
from pyonpyin.storage import get_store, storage_backend
from pyonpyin.audio import tts_configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create a local .env with unique credentials; preserve existing files")
    commands.add_parser("doctor", help="Print configuration readiness, never secret values")
    backup = commands.add_parser("backup", help="Back up the database; back up the audio directory separately")
    backup.add_argument("target")
    options = parser.parse_args()
    if options.command == "init":
        destination = Path(".env")
        if destination.exists():
            raise SystemExit(".env already exists; it was not changed.")
        template = Path(".env.example").read_text(encoding="utf-8")
        template = template.replace("PYONPYIN_ADMIN_PASSWORD=\n", "PYONPYIN_ADMIN_PASSWORD=" + secrets.token_urlsafe(24) + "\n")
        template = template.replace("PYONPYIN_SESSION_SECRET=\n", "PYONPYIN_SESSION_SECRET=" + secrets.token_urlsafe(48) + "\n")
        with destination.open("x", encoding="utf-8", newline="\n") as output:
            output.write(template)
        print("Created .env. Open it locally for the generated admin password; no secret was printed.")
    load_environment()
    store = get_store()
    if options.command == "backup":
        if not hasattr(store, "backup"):
            raise SystemExit("This backup command requires SQLite storage.")
        store.backup(options.target)
        print("Database backup completed. Include the audio folder in your backup plan.")
    elif options.command == "doctor":
        print(json.dumps({
            "database": storage_backend(), "database_readable": isinstance(store.read_records("Story Library"), list),
            "admin_password_configured": bool(os.environ.get("PYONPYIN_ADMIN_PASSWORD")),
            "session_secret_configured": bool(os.environ.get("PYONPYIN_SESSION_SECRET")),
            "gemini_key_configured": bool(os.environ.get("GEMINI_API_KEY")),
            "azure_key_configured": bool(os.environ.get("AZURE_SPEECH_KEY")),
            "azure_region_configured": bool(os.environ.get("AZURE_SPEECH_REGION")),
            **tts_configuration(),
            "publishing_enabled": os.environ.get("PYONPYIN_PUBLISHING_ENABLED") == "true",
            "external_services_tested": False,
        }, indent=2))


if __name__ == "__main__":
    main()
