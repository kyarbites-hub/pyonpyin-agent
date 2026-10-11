# PyonPyin AI Agent
# Standard Ebooks မှ စာအုပ်အသစ်စာရင်း ရယူခြင်း

import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


# Repository ရဲ့ အခြေခံလမ်းကြောင်းကို ရှာမယ်
BASE_DIR = Path(__file__).resolve().parent.parent

# Source စာရင်းရှိတဲ့ JSON ဖိုင်
SOURCES_FILE = BASE_DIR / "data" / "approved_sources.json"


def load_approved_sources():
    """အတည်ပြုထားတဲ့ Source တွေကို ဖတ်မယ်။"""

    with SOURCES_FILE.open("r", encoding="utf-8") as file:
        sources = json.load(file)

    # အတည်ပြုပြီး automation ခွင့်ပြုထားတဲ့ Source တွေကိုသာ ရွေးမယ်
    return [
        source for source in sources
        if source.get("approval_status") == "APPROVED"
        and source.get("automation_allowed") is True
    ]


def fetch_new_books(feed_url):
    """RSS/Atom feed မှ စာအုပ်အသစ်စာရင်းကို ရယူမယ်။"""

    # အင်တာနက်တောင်းဆိုမှုကို သတ်မှတ်ချိန်အတွင်း ပြီးစေမယ်
    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "PyonPyinAgent/1.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        xml_data = response.read()

    # Atom feed ကို XML အဖြစ် ဖတ်မယ်
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
            # စာအုပ်တစ်အုပ်ချင်းစီရဲ့ လိုင်စင်ကို နောက်ထပ်စစ်ဆေးရမယ်
            "status": "NEEDS_LICENSE_REVIEW"
        })

    return books


def main():
    """Story Finder ကို စမ်းသပ်မယ်။"""

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
            print(f"Could not fetch books: {error}")
            raise


if __name__ == "__main__":
    main()
