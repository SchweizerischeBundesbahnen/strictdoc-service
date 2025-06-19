"""Input sanitization utilities for StrictDoc service."""

import re
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks.

    Args:
        filename: The filename to sanitize

    Returns:
        str: The sanitized filename
    """
    # Remove any path components, only keep the base filename
    sanitized = Path(filename).name

    # Additional sanitization - keep only alphanumeric chars, underscore, hyphen, and dot
    sanitized = re.sub(r"[^\w.-]", "_", sanitized)

    # Ensure the filename is not empty or starts with a dot
    if not sanitized or sanitized.startswith("."):
        sanitized = "document" + sanitized

    return sanitized


def sanitize_for_logging(text: str) -> str:
    """Sanitize text for safe logging by removing control characters.

    Prevents log injection attacks by removing newlines and carriage returns.

    Args:
        text: The text to sanitize

    Returns:
        str: The sanitized text safe for logging
    """
    if not isinstance(text, str):
        text = str(text)

    # Remove newlines and carriage returns to prevent log injection
    return text.replace("\n", "").replace("\r", "")


def normalize_line_endings(content: str) -> str:
    """Normalize line endings to Unix style.

    Args:
        content: The content with potentially mixed line endings

    Returns:
        str: Content with normalized line endings
    """
    # Normalize line endings to Unix style
    return content.replace("\r\n", "\n").replace("\r", "\n")


def sanitize_path_component(path_component: str) -> str:
    """Sanitize a path component to prevent directory traversal.

    Args:
        path_component: The path component to sanitize

    Returns:
        str: The sanitized path component
    """
    # Remove any dangerous path components
    sanitized = re.sub(r"[/\\\.]{2,}", "_", path_component)
    sanitized = sanitized.replace("..", "_")
    sanitized = sanitized.strip("./\\")

    # Handle whitespace-only strings
    if not sanitized or not sanitized.strip():
        sanitized = "safe_component"

    return sanitized
