"""Input sanitization utilities for StrictDoc service."""

import re


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

    # Remove control characters and newlines to prevent log injection
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    return text.replace("\n", " ").replace("\r", " ")


def normalize_line_endings(content: str) -> str:
    """Normalize line endings to Unix style.

    Args:
        content: The content with potentially mixed line endings

    Returns:
        str: Content with normalized line endings
    """
    return content.replace("\r\n", "\n").replace("\r", "\n")
