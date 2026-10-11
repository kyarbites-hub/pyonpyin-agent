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
    """Google Sheets မှ လိုင်စင်အတည်ပြုထားတဲ့ စာအုပ်တွေကိုသာ ဖတ်မယ်။"""

    # SourceQueue ထဲက လိုင်စင်အခြေအနေကို ဖတ်မယ်
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="SourceQueue!A2:G"
    ).execute()

    rows = result.get("values", [])
    approved_books = []

    for row in rows:
        # ကော်လံ ၇ ခု မပြည့်စုံရင် ကျော်မယ်
        if len(row) < 7:
            continue

        title = row[0].strip()
        source_url = row[1].strip()
        source_name = row[2].strip()
        license_status = row[3].strip().upper()
        evidence_url = row[5].strip()
        reviewer = row[6].strip()

        # လိုင်စင်အတည်ပြုပြီး အထောက်အထားနဲ့ စစ်ဆေးသူပါမှသာ ခွင့်ပြုမယ်
        if (
            license_status == "APPROVED"
            and evidence_url
            and reviewer
            and title
            and source_url
        ):
            approved_books.append({
                "title": title,
                "url": source_url,
                "source_name": source_name,
                "license_status": license_status,
                "license_evidence": evidence_url,
                "reviewer": reviewer
            })

    print(f"License-approved books: {len(approved_books)}")

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
def main():
    """PyonPyin AI Agent ရဲ့ အဓိကလုပ်ဆောင်ချက်။"""

    try:
        # အဆင့် ၁: Google Sheets နဲ့ ချိတ်ဆက်မယ်
        print("Connecting to Google Sheets...")
        service = connect_google_sheets()

        # အဆင့် ၂: လိုင်စင်အတည်ပြုထားတဲ့စာအုပ်တွေကို ဖတ်မယ်
        print("Checking license-approved books...")
        approved_books = get_license_approved_books(service)

        # အဆင့် ၃: ရလဒ်ကို ပြမယ်
        print(
            f"Books approved for next stage: "
            f"{len(approved_books)}"
        )

        # အဆင့် ၄: လက်ရှိမှာ AI ဆီ မပို့သေးဘူး
        print("License review check completed.")
        print("AI story generation is not started yet.")
        print("Auto publishing is disabled.")

    except Exception as error:
        # ပြဿနာရှိရင် Error ကို ပြမယ်
        print(f"Story Finder failed: {error}")
        raise


if __name__ == "__main__":
    main()
