"""Deterministic document forensics (TRU-03). No model is involved and nothing here ever approves anything: a signal only adds a flag,
and any flag stops Lipik from upgrading a claim, so a person decides (I-1, I-2).

Signals are evidence of *editing*, not proof of fraud: a genuine PDF can be re-saved. The wording of each flag says so.
"""
from __future__ import annotations

import io
import re

from PIL import ExifTags, Image, UnidentifiedImageError

# Software that edits or composes pictures and pages. A credential straight from an issuer is rarely produced by these.
EDITORS = ("photoshop", "gimp", "canva", "paint.net", "pixlr", "snapseed", "illustrator", "inkscape", "affinity", "ilovepdf", "smallpdf", "sejda")


def _editor_in(text: str) -> str | None:
    low = text.lower()
    return next((e for e in EDITORS if e in low), None)


def _pdf_field(data: bytes, key: bytes) -> str:
    m = re.search(rb"/" + key + rb"\s*\(([^)]{0,200})\)", data)
    return m.group(1).decode("latin-1", "replace") if m else ""


def pdf_signals(data: bytes) -> list[str]:
    flags: list[str] = []
    # Each incremental update appends a new %%EOF, so more than one means the file was changed after it was first written.
    if len(re.findall(rb"%%EOF", data)) > 1:
        flags.append("pdf_edited_after_creation")
    if _editor_in(" ".join(_pdf_field(data, k) for k in (b"Producer", b"Creator"))):
        flags.append("edited_with_image_or_pdf_editor")
    created, modified = _pdf_field(data, b"CreationDate"), _pdf_field(data, b"ModDate")
    if created and modified and created[2:16] != modified[2:16]:
        flags.append("pdf_modified_after_creation_date")
    return flags


def image_signals(data: bytes) -> list[str]:
    try:
        exif = Image.open(io.BytesIO(data)).getexif()
    except (UnidentifiedImageError, OSError):
        return []
    software = str(exif.get(next((k for k, v in ExifTags.TAGS.items() if v == "Software"), -1), ""))
    return ["edited_with_image_or_pdf_editor"] if _editor_in(software) else []


def forensic_flags(content_type: str, data: bytes) -> list[str]:
    """Every signal found, deduplicated, in a stable order."""
    found = pdf_signals(data) if content_type == "application/pdf" else image_signals(data) if content_type.startswith("image/") else []
    return list(dict.fromkeys(found))


FLAG_TEXT = {
    "pdf_edited_after_creation": "The PDF was changed after it was first saved (this can be innocent, a person should look).",
    "edited_with_image_or_pdf_editor": "The file was produced or edited with a picture or PDF editor.",
    "pdf_modified_after_creation_date": "The PDF's modified date differs from its creation date.",
    "duplicate_document": "This exact file is already attached to another profile.",
}
