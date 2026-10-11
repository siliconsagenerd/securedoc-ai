"""Extract plain text from uploaded documents.

Content is handled entirely in memory; nothing is written to disk, so there is no
temporary file to clean up. Only the four declared formats are supported, and the
caller is expected to have validated the upload first.
"""

from __future__ import annotations

from io import BytesIO


class ExtractionError(Exception):
    """Raised when a document cannot be read or yields no usable text."""


def extract_text(filename: str, data: bytes) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if suffix in ("txt", "md"):
        text = data.decode("utf-8", errors="replace")
    elif suffix == "pdf":
        text = _from_pdf(data)
    elif suffix == "docx":
        text = _from_docx(data)
    else:
        raise ExtractionError(f"unsupported file type: .{suffix or '(none)'}")

    text = text.strip()
    if not text:
        raise ExtractionError("no extractable text found in document")
    return text


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf raises a variety of errors on malformed input
        raise ExtractionError("could not read PDF document") from exc


def _from_docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise ExtractionError("could not read DOCX document") from exc
