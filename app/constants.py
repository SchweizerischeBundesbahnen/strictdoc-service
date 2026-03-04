"""Shared constants for StrictDoc service."""

# Define supported export formats with their file extensions and mime types
EXPORT_FORMATS = {
    "doxygen": {"extension": "xml", "mime_type": "application/xml"},
    "excel": {"extension": "xlsx", "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "html": {"extension": "zip", "mime_type": "application/zip"},
    "html2pdf": {"extension": "pdf", "mime_type": "application/pdf"},
    "json": {"extension": "json", "mime_type": "application/json"},
    "reqif-sdoc": {"extension": "reqif", "mime_type": "application/xml"},
    "reqifz-sdoc": {"extension": "reqifz", "mime_type": "application/zip"},
    "rst": {"extension": "rst", "mime_type": "text/x-rst"},
    "sdoc": {"extension": "sdoc", "mime_type": "text/plain"},
    "spdx": {"extension": "spdx", "mime_type": "text/plain"},
}

# Frozenset of valid export format names (derived from EXPORT_FORMATS)
VALID_EXPORT_FORMATS: frozenset[str] = frozenset(EXPORT_FORMATS.keys())
