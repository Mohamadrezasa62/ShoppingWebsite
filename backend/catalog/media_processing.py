from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile

MAX_UPLOAD = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000


def normalize_image(upload):
    if upload is None or upload.size > MAX_UPLOAD or upload.size == 0:
        raise ValueError("invalid_image_size")
    raw = upload.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise ValueError("invalid_image_size")
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in ("JPEG", "PNG", "WEBP") or source.width * source.height > MAX_PIXELS:
                raise ValueError("invalid_image_format")
            source.verify()
        with Image.open(BytesIO(raw)) as source:
            source.load()
            # New pixel-only image excludes original metadata and embedded payloads.
            source = ImageOps.exif_transpose(source)
            image = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            image.thumbnail((2000, 2000))
            clean = Image.new(image.mode, image.size)
            clean.paste(image)
            result = BytesIO()
            clean.save(result, format="PNG")
        if result.tell() > MAX_UPLOAD:
            raise ValueError("normalized_image_too_large")
        return ContentFile(result.getvalue(), name=f"{uuid4().hex}.png")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("invalid_image") from error
