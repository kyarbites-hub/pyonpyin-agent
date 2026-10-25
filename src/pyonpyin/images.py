"""Validated, metadata-free image uploads for optional story covers and home artwork."""

import io
import os
import uuid
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


def image_directory():
    return Path(os.environ.get("IMAGE_OUTPUT_DIR", "data/runtime/images")).resolve()


def save_image(upload):
    # Extension ကို မယုံဘဲ ဖိုင်အတွင်းက ပုံကိုဖတ်စစ်ပြီး EXIF အချက်အလက်များဖယ်ကာ ဖိုင်အသစ် သိမ်းသည်။
    data = upload.read(MAX_IMAGE_BYTES + 1)
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Choose a JPG, PNG or WebP image of at most 8 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "is_animated", False):
                    raise ValueError("Only still JPG, PNG and WebP images are supported.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((2400, 2400))
                output = io.BytesIO()
                image.save(output, format="WEBP", quality=90)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("The image is invalid or its dimensions are too large.") from exc
    directory = image_directory()
    directory.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + ".webp"
    with (directory / filename).open("xb") as target:
        target.write(output.getvalue())
    return "/media/images/" + filename
