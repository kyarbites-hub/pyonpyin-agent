"""Small .env loader: literal values, no shell execution or interpolation."""

import os
import re
from pathlib import Path


def load_environment():
    path = Path(os.environ.get("PYONPYIN_ENV_FILE", ".env"))
    if not path.exists():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise RuntimeError(f"Invalid environment setting on line {number}.")
        if value[:1] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                raise RuntimeError(f"Unclosed environment value on line {number}.")
            value = value[1:-1]
        # စက်၏ environment ထဲမှာ ရှိပြီးသားတန်ဖိုးကို .env ဖြင့် မရေးထပ်ပါ။
        os.environ.setdefault(key, value)
