"""Utilities for input sanitization in the StrictDoc service."""

import re


def sanitize_for_logging(text: str, max_length: int = 1000) -> str:
    """
    Sanitize text for safe logging by:
    - Converting non-string input to string
    - Removing all control characters
    - Replacing newlines with spaces
    - Truncating to `max_length` and appending '...[truncated]' if necessary

    Args:
        text (str): The input text to sanitize.
        max_length (int, optional): Maximum allowed length of the sanitized text. Defaults to 1000.

    Returns:
        str: The sanitized text safe for logging.
    """
    if not isinstance(text, str):
        text = str(text)

    # Remove all control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    # Replace newlines with spaces
    text = text.replace("\n", " ").replace("\r", " ")

    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "...[truncated]"

    return text


def normalize_line_endings(content: str) -> str:
    """
    Normalize all line endings in the input content to Unix style (`\n`).

    Args:
        content (str): The content with potentially mixed line endings.

    Returns:
        str: Content with all line endings normalized to `\n`.
    """
    return content.replace("\r\n", "\n").replace("\r", "\n")
