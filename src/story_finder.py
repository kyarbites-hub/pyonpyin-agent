
# PyonPyin AI Agent - Story Finder
# ရည်ရွယ်ချက် - ပုံပြင်ရှာဖွေရေးအတွက် အခြေခံစနစ်တည်ဆောက်ခြင်း

import json
from pathlib import Path


# approved_sources.json ရှိတဲ့နေရာကို ရှာပေးခြင်း
BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_FILE = BASE_DIR / "data" / "approved_sources.json"


def load_approved_sources():
    """အတည်ပြုထားသော Source များကို ဖတ်ယူမည်။"""

    # Source ဖိုင်မရှိလျှင် Error ပြမည်
    if not SOURCES_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCES_FILE}"
        )

    # JSON ဖိုင်ကို ဖတ်ယူမည်
    with SOURCES_FILE.open("r", encoding="utf-8") as file:
        sources = json.load(file)

    # List ပုံစံဖြစ်ကြောင်း စစ်ဆေးမည်
    if not isinstance(sources, list):
        raise ValueError("Sources file must contain a list.")

    return sources


def get_approved_sources():
    """အလိုအလျောက်အသုံးပြုခွင့်ပေးထားသော Source များကိုသာ ရွေးမည်။"""

    sources = load_approved_sources()

    # Human က APPROVED ပေးပြီး automation_allowed ဖွင့်ထားမှ ရွေးမည်
    return [
        source
        for source in sources
        if source.get("approval_status") == "APPROVED"
        and source.get("automation_allowed") is True
    ]


def main():
    """Story Finder ကို စမ်းသပ်ရန် အဓိကလုပ်ဆောင်ချက်။"""

    sources = get_approved_sources()

    print(f"Approved sources found: {len(sources)}")

    for source in sources:
        print(f"- {source.get('source_name', 'Unknown source')}")
        print(f"  URL: {source.get('url', 'No URL')}")


if __name__ == "__main__":
    main()
