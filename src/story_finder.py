# PyonPyin AI Agent
# Standard Ebooks မှ စာအုပ်အသစ်ရှာပြီး Google Sheets ချိတ်ဆက်မှု စမ်းသပ်ခြင်း

import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# Repository ရဲ့ အခြေခံလမ်းကြောင်းကို ရှာမယ်
BASE_DIR = Path(__file__).resolve().parent.parent

# Source စာရင်းရှိတဲ့ JSON ဖိုင်
SOURCES_FILE = BASE_DIR / "data" / "approved_sources.json"

# Google Sheets API အတွက် လိုအပ်တဲ့ ခွင့်ပြုချက်
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Google Sheet ID
SPREADSHEET_ID = "1qTC6NH6HM4sIo6XT-C4fffaVK1eQ44MGL6fARQ07uI4"

# စမ်းသပ်ဖတ်ရှုမယ့် Sheet အမည်နှင့် Range
SHEET_RANGE = "SourceQueue!A1:E1"


def load_approved_sources():
    """အတည်ပြုပြီး Automation ခွင့်ပြုထားတဲ့ Source တွေကိုသာ ရွေးမယ်။"""

    with SOURCES_FILE.open("r", encoding="utf-8") as file:
        sources = json.load(file)

    return [
        source for source in sources
        if source.get("approval_status") == "APPROVED"
        and source.get("automation_allowed") is True
    ]


def connect_google_sheets():
    """GitHub Secret ထဲက OAuth Token ကို အသုံးပြုပြီး Sheets API ချိတ်မယ်။"""

    token_json = os.environ.get("GOOGLE_TOKEN_JSON")

    if not token_json:
        raise RuntimeError(
            "GOOGLE_TOKEN_JSON Secret မတွေ့ပါ။ "
            "GitHub Repository Settings ကို စစ်ဆေးပါ။"
        )

    # Token အချက်အလက်ကို Environment Variable ကနေ ဖတ်မယ်
    token_info = json.loads(token_json)

    credentials = Credentials.from_authorized_user_info(
        token_info,
        scopes=SCOPES
    )

    # Google Sheets API Service တည်ဆောက်မယ်
    service = build(
        "sheets",
        "v4",
        credentials=credentials,
        cache_discovery=False
    )

    return service


def test_google_sheets(service):
    """Stories Sheet ရဲ့ Header တွေကိုသာ ဖတ်ပြီး ချိတ်ဆက်မှု စမ်းမယ်။"""

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=SHEET_RANGE
    ).execute()

    headers = result.get("values", [])

    if not headers:
        print("⚠️ Stories Sheet မှာ Header မတွေ့ပါ။")
        return

    print("✅ Google Sheets ချိတ်ဆက်မှု အောင်မြင်ပါပြီ!")
    print("Headers:", headers[0])


def fetch_new_books(feed_url):
    """Atom feed မှ စာအုပ်စာရင်းကို ရယူမယ်။"""

    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "PyonPyinAgent/1.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    books = []

    for entry in root.findall("atom:entry", namespace):
        title_element = entry.find("atom:title", namespace)
        link_element = entry.find("atom:link", namespace)

        if title_element is None or link_element is None:
            continue

        books.append({
            "title": title_element.text or "Untitled",
            "url": link_element.attrib.get("href", ""),
            "status": "NEEDS_LICENSE_REVIEW"
        })

    return books


def main():
    """Google Sheets ကို စမ်းသပ်ပြီး Story Finder ကို ဆက်လည်ပတ်မယ်။"""

    # အဆင့် 1: Google Sheets ချိတ်ဆက်မှုကို စမ်းမယ်
    print("Connecting to Google Sheets...")

    service = connect_google_sheets()
    test_google_sheets(service)

    # အဆင့် 2: အတည်ပြုထားတဲ့ Source တွေက စာအုပ်စာရင်းကို ရှာမယ်
    sources = load_approved_sources()

    for source in sources:
        feed_url = source.get("feed_url")

        if not feed_url:
            print(f"Skipping {source.get('source_name')}: no feed URL")
            continue

        print(f"\nChecking source: {source['source_name']}")

        try:
            books = fetch_new_books(feed_url)
            print(f"Books found: {len(books)}")

            for book in books[:5]:
                print(f"- {book['title']}")
                print(f"  URL: {book['url']}")
                print(f"  Status: {book['status']}")

        except Exception as error:
            # Token သို့မဟုတ် လျှို့ဝှက်အချက်အလက်ကို မထုတ်ပြဘဲ Error ကို ပြမယ်
            print(f"Could not fetch books: {type(error).__name__}")
            raise


if __name__ == "__main__":
    main()
