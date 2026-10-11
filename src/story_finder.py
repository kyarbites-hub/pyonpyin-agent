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
def get_license_approved_books(service):
    """လူကိုယ်တိုင် စစ်ဆေးအတည်ပြုထားသော စာအုပ်များကို ရယူမယ်။"""

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="SourceQueue!A2:G"
    ).execute()

    rows = result.get("values", [])
    approved_books = []

    for row in rows:
        # ကော်လံ ၇ ခု ပြည့်စုံအောင် စစ်မယ်
        row += [""] * (7 - len(row))

        title = row[0].strip()
        source_url = row[1].strip()
        license_status = row[3].strip().upper()
        license_evidence = row[5].strip()
        human_reviewer = row[6].strip()

        # အထောက်အထားနဲ့ လူကိုယ်တိုင်စစ်ဆေးသူ ရှိမှ လက်ခံမယ်
        if (
            title
            and source_url
            and license_status == "APPROVED"
            and license_evidence
            and human_reviewer
        ):
            approved_books.append({
                "title": title,
                "source_url": source_url,
                "source_name": row[2].strip(),
                "license_status": license_status,
                "license_evidence": license_evidence,
                "human_reviewer": human_reviewer,
            })

    print(
        f"Human-reviewed, license-approved books: "
        f"{len(approved_books)}"
    )

    return approved_books

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
def remove_duplicate_books(books):
    """URL တူညီတဲ့ စာအုပ်တွေကို တစ်အုပ်တည်းသာ ထားမယ်။"""

    unique_books = []
    seen_urls = set()

    for book in books:
        # URL ကို ဖတ်ပြီး အပို Space တွေ ဖယ်ရှားမယ်
        book_url = book.get("url", "").strip().rstrip("/")

        # URL မရှိရင် ကျော်မယ်
        if not book_url:
            continue

        # URL တူပြီးသားဆိုရင် ထပ်မထည့်ဘူး
        if book_url in seen_urls:
            continue

        seen_urls.add(book_url)
        unique_books.append(book)

    print(f"Books after duplicate check: {len(unique_books)}")

    return unique_books
def filter_existing_books(service, books):
    """Google Sheets ထဲမှာ ရှိပြီးသားစာအုပ်တွေကို ဖယ်ရှားမယ်။"""

    # SourceQueue ထဲက ရှိပြီးသား URL တွေကို ဖတ်မယ်
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="SourceQueue!A2:G"
    ).execute()

    rows = result.get("values", [])

    # ရှိပြီးသား URL တွေကို Set ထဲမှာ သိမ်းမယ်
    existing_urls = set()

    for row in rows:
        if len(row) > 1 and row[1].strip():
            existing_urls.add(row[1].strip().rstrip("/"))

    # Sheet ထဲမှာ မရှိသေးတဲ့စာအုပ်တွေကိုသာ ရွေးမယ်
    new_books = []

    for book in books:
        url = book.get("url", "").strip().rstrip("/")

        if url and url not in existing_urls:
            new_books.append(book)

    print(f"New books not in Google Sheets: {len(new_books)}")

    return new_books
def main():
    """PyonPyin AI Agent ရဲ့ အဓိကလုပ်ဆောင်ချက်။"""

    try:
        # အဆင့် ၁: Google Sheets ကို ချိတ်ဆက်မယ်
        print("Connecting to Google Sheets...")
        service = connect_google_sheets()

        # အဆင့် ၂: လိုင်စင်အတည်ပြုထားတဲ့စာအုပ်တွေကို ဖတ်မယ်
        approved_books = get_license_approved_books(service)

        print(
            f"License-approved books: {len(approved_books)}"
        )

        # အဆင့် ၃: အတည်ပြုထားတဲ့စာအုပ်စာရင်းကို ပြမယ်
        for book in approved_books:
            print(f"Approved title: {book['title']}")
            print(f"Source URL: {book['source_url']}")
            print(f"Reviewed by: {book['human_reviewer']}")

        # အဆင့် ၄: Source စာရင်းကို ဖတ်မယ်
        sources = load_approved_sources()

        for source in sources:
            feed_url = source.get("feed_url")

            # Feed URL မရှိရင် ကျော်မယ်
            if not feed_url:
                continue

            print(f"\nChecking source: {source['source_name']}")

            # အဆင့် ၅: စာအုပ်အသစ်တွေကို ရှာမယ်
            books = fetch_new_books(feed_url)
            print(f"Books found: {len(books)}")

            # အဆင့် ၆: ထပ်နေတဲ့စာအုပ်တွေကို ဖယ်မယ်
            books = remove_duplicate_books(books)

            # အဆင့် ၇: ရှိပြီးသားစာအုပ်တွေကို ဖယ်မယ်
            new_books = filter_existing_books(service, books)

            print(f"New books ready for review: {len(new_books)}")

            # အဆင့် ၈: စာအုပ်အသစ်တွေကို Google Sheets ထဲ သိမ်းမယ်
            if new_books:
                save_books_to_sheet(
                    service,
                    new_books,
                    source["source_name"]
                )

                print(f"Saved {len(new_books)} new books.")
            else:
                print("No new books to save.")

        print("\nStory Finder completed successfully.")
        print("License review is required for unapproved books.")
        print("AI story generation has not started.")
        print("Auto publishing remains disabled.")

    except Exception as error:
        # Error အမျိုးအစားကိုသာ ပြမယ်၊ Secret တွေကို မထုတ်ပြဘူး
        print(f"Story Finder failed: {type(error).__name__}")
        raise


if __name__ == "__main__":
    main()
