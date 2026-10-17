import os
import mimetypes

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

SUPPORTED_EXTENSIONS = {
    # PDF
    "pdf": "PDF Document",
    # Microsoft Word
    "doc": "Word Document",
    "docx": "Word Document",
    # Microsoft Excel
    "xls": "Excel Spreadsheet",
    "xlsx": "Excel Spreadsheet",
    "xlsm": "Excel Macro-Enabled Spreadsheet",
    "csv": "CSV Document",
    # Microsoft Project & Schedules
    "mpp": "Microsoft Project Plan",
    "xml": "Project XML / MSPDI",
    "mspdi": "Microsoft Project XML",
    "xer": "Primavera Schedule Export",
    # PowerPoint
    "ppt": "PowerPoint Presentation",
    "pptx": "PowerPoint Presentation",
    # Images
    "png": "PNG Image",
    "jpg": "JPEG Image",
    "jpeg": "JPEG Image",
    "webp": "WebP Image",
    # Text / OpenDoc
    "txt": "Plain Text Document",
    "rtf": "Rich Text Document",
    "odt": "OpenDocument Text",
    "ods": "OpenDocument Spreadsheet",
}


def validate_file_content(uploaded_file):
    """
    Validates uploaded file size, extension, and verifies header magic bytes
    to ensure the file matches its declared content type.
    """
    # 1. Size check
    file_size = uploaded_file.size
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        return {
            "valid": False,
            "error": f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed limit of {max_mb} MB.",
        }

    # 2. Extension check
    filename = uploaded_file.name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))
        return {
            "valid": False,
            "error": f"Unsupported file format '.{ext}'. Supported formats: {allowed}",
        }

    # 3. Read header bytes (first 512 bytes)
    uploaded_file.seek(0)
    header = uploaded_file.read(512)
    uploaded_file.seek(0)

    # Magic byte signatures
    is_pdf = header.startswith(b"%PDF-")
    is_zip = header.startswith(b"PK\x03\x04")  # docx, xlsx, pptx, odt, ods
    is_ole = header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")  # doc, xls, ppt, binary mpp
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_webp = len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    is_xml_text = header.strip().startswith(b"<?xml") or header.strip().startswith(b"<")

    # Content signature verification
    if ext == "pdf" and not is_pdf:
        return {"valid": False, "error": "Invalid PDF file: corrupted or fake PDF header."}
    if ext in ["docx", "xlsx", "xlsm", "pptx", "odt", "ods"] and not is_zip:
        return {"valid": False, "error": f"Invalid Office document: '{filename}' is corrupted or not a valid archive."}
    if ext in ["png"] and not is_png:
        return {"valid": False, "error": "Invalid image: not a valid PNG file."}
    if ext in ["jpg", "jpeg"] and not is_jpeg:
        return {"valid": False, "error": "Invalid image: not a valid JPEG file."}
    if ext in ["webp"] and not is_webp:
        return {"valid": False, "error": "Invalid image: not a valid WebP file."}
    if ext in ["xml", "mspdi"] and not is_xml_text:
        return {"valid": False, "error": "Invalid XML file: file does not start with valid XML markup."}

    # Resolve detected MIME type
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return {
        "valid": True,
        "extension": ext.upper(),
        "mimeType": mime_type,
        "sizeBytes": file_size,
        "formatDescription": SUPPORTED_EXTENSIONS[ext],
        "isSchedule": ext in ["mpp", "xml", "mspdi", "xer"],
    }
