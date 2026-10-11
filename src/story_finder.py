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


def save_books_to_sheet(service, books, source_name):
    """စာအုပ်စာရင်းကို SourceQueue ထဲ သိမ်းမယ်။"""

    # လက်ရှိစာရင်းကို ဖတ်ပြီး ထပ်နေတဲ့ URL တွေကို စစ်မယ်
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="SourceQueue!A2:E"
    ).execute()

    existing_rows = result.get("values", [])

    # ရှိပြီးသား Source URL တွေကို Set ထဲထည့်မယ်
    existing_urls = {
        row[1]
        for row in existing_rows
        if len(row) > 1 and row[1]
    }

    new_rows = []

    for book in books:
        url = book.get("url", "").strip()

        # URL မရှိရင်၊ ရှိပြီးသား URL ဖြစ်ရင် ကျော်မယ်
        if not url or url in existing_urls:
            continue

        new_rows.append([
            book.get("title", "Untitled"),
            url,
            source_name,
            "NEEDS_LICENSE_REVIEW",
            "PENDING_REVIEW"
        ])

        # ဒီတစ်ကြိမ်အတွင်း ထပ်နေမှုကိုလည်း ကာကွယ်မယ်
        existing_urls.add(url)

    if not new_rows:
        print("New books to save: 0")
        return

    # စာအုပ်အသစ်တွေကို Sheet ရဲ့ အောက်ဆုံးမှာ ထည့်မယ်
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="SourceQueue!A:E",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": new_rows}
    ).execute()

    print(f"New books saved: {len(new_rows)}")


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

            # စာအုပ်စာရင်းကို Google Sheets ထဲ သိမ်းမယ်
            save_books_to_sheet(
                service,
                books,
                source["source_name"]
            )

        except Exception as error:
            print(f"Could not fetch or save books: {type(error).__name__}")
            raise


if __name__ == "__main__":
    main()
