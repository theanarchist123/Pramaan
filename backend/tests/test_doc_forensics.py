import io

from PIL import Image

from app.services.doc_forensics import forensic_flags

CLEAN_PDF = b"%PDF-1.4\n1 0 obj<</Producer(Registrar Office ERP)/CreationDate(D:20240101120000Z)/ModDate(D:20240101120000Z)>>endobj\n%%EOF\n"


def test_a_clean_single_save_pdf_raises_nothing():
    assert forensic_flags("application/pdf", CLEAN_PDF) == []


def test_an_incrementally_updated_pdf_is_flagged_as_edited():
    assert "pdf_edited_after_creation" in forensic_flags("application/pdf", CLEAN_PDF + b"2 0 obj<<>>endobj\n%%EOF\n")


def test_a_pdf_made_by_an_editor_is_flagged():
    pdf = CLEAN_PDF.replace(b"Registrar Office ERP", b"Adobe Photoshop 25")
    assert forensic_flags("application/pdf", pdf) == ["edited_with_image_or_pdf_editor"]


def test_modified_date_differing_from_creation_date_is_flagged():
    pdf = CLEAN_PDF.replace(b"/ModDate(D:20240101120000Z)", b"/ModDate(D:20250611090000Z)")
    assert forensic_flags("application/pdf", pdf) == ["pdf_modified_after_creation_date"]


def _jpeg(software: str | None) -> bytes:
    img, buf = Image.new("RGB", (8, 8), "white"), io.BytesIO()
    exif = Image.Exif()
    if software:
        exif[0x0131] = software  # EXIF "Software"
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_an_image_saved_by_an_editor_is_flagged_and_a_plain_one_is_not():
    assert forensic_flags("image/jpeg", _jpeg("Adobe Photoshop 25.1")) == ["edited_with_image_or_pdf_editor"]
    assert forensic_flags("image/jpeg", _jpeg(None)) == []


def test_garbage_never_raises_and_text_is_ignored():
    assert forensic_flags("image/png", b"not an image") == []
    assert forensic_flags("text/plain", b"hello") == []
