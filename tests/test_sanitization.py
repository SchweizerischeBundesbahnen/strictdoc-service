"""Tests for the sanitization module."""

import pytest
from pathvalidate import sanitize_filename

from app.sanitization import (
    sanitize_for_logging,
    normalize_line_endings,
)


class TestSanitizeForLogging:
    """Test cases for sanitize_for_logging function."""

    def test_normal_text(self) -> None:
        """Test that normal text is preserved."""
        assert sanitize_for_logging("normal text") == "normal text"
        assert sanitize_for_logging("numbers 123") == "numbers 123"

    def test_newline_removal(self) -> None:
        """Test that newlines are removed."""
        assert sanitize_for_logging("line1\nline2") == "line1line2"
        assert sanitize_for_logging("line1\r\nline2") == "line1line2"
        assert sanitize_for_logging("line1\rline2") == "line1line2"

    def test_mixed_line_endings(self) -> None:
        """Test handling of mixed line endings."""
        text = "line1\nline2\r\nline3\rline4"
        expected = "line1line2line3line4"
        assert sanitize_for_logging(text) == expected

    def test_non_string_input(self) -> None:
        """Test handling of non-string input."""
        assert sanitize_for_logging(123) == "123"
        assert sanitize_for_logging(None) == "None"
        assert sanitize_for_logging(["list"]) == "['list']"

    def test_special_characters_preserved(self) -> None:
        """Test that other special characters are preserved."""
        assert sanitize_for_logging("test@#$%^&*()") == "test@#$%^&*()"
        assert sanitize_for_logging("unicode: ñáéíóú") == "unicode: ñáéíóú"


class TestNormalizeLineEndings:
    """Test cases for normalize_line_endings function."""

    def test_unix_line_endings(self) -> None:
        """Test that Unix line endings are preserved."""
        text = "line1\nline2\nline3"
        assert normalize_line_endings(text) == text

    def test_windows_line_endings(self) -> None:
        """Test that Windows line endings are converted."""
        text = "line1\r\nline2\r\nline3"
        expected = "line1\nline2\nline3"
        assert normalize_line_endings(text) == expected

    def test_mac_line_endings(self) -> None:
        """Test that Mac line endings are converted."""
        text = "line1\rline2\rline3"
        expected = "line1\nline2\nline3"
        assert normalize_line_endings(text) == expected

    def test_mixed_line_endings(self) -> None:
        """Test handling of mixed line endings."""
        text = "line1\nline2\r\nline3\rline4"
        expected = "line1\nline2\nline3\nline4"
        assert normalize_line_endings(text) == expected

    def test_empty_string(self) -> None:
        """Test handling of empty string."""
        assert normalize_line_endings("") == ""

    def test_no_line_endings(self) -> None:
        """Test handling of text without line endings."""
        text = "single line"
        assert normalize_line_endings(text) == text


class TestSanitizationIntegration:
    """Integration tests for sanitization functions."""

    def test_filename_with_logging_sanitization(self) -> None:
        """Test combining filename and logging sanitization."""
        dangerous_filename = "../../../etc/passwd\nwith\rlinebreaks"
        safe_filename = sanitize_filename(dangerous_filename, replacement_text="_")
        safe_for_log = sanitize_for_logging(dangerous_filename)

        assert safe_filename == ".._.._.._etc_passwd_with_linebreaks"
        assert safe_for_log == "../../../etc/passwdwithlinebreaks"

    def test_content_processing_workflow(self) -> None:
        """Test the typical content processing workflow."""
        content = "line1\r\nline2\rline3\n"
        normalized = normalize_line_endings(content)
        log_safe = sanitize_for_logging("Processing content\nwith linebreaks")

        assert normalized == "line1\nline2\nline3\n"
        assert log_safe == "Processing contentwith linebreaks"

    def test_real_world_scenarios(self) -> None:
        """Test real-world scenarios from the application."""
        # Scenario 1: User uploads file with dangerous name
        user_filename = "../../secret\nfile.pdf"
        safe_name = sanitize_filename(user_filename)
        assert safe_name == "....secretfile.pdf"

        # Scenario 2: Logging user input safely
        user_format = "html\nmalicious\rcode"
        log_safe = sanitize_for_logging(user_format)
        assert log_safe == "htmlmaliciouscode"

        # Scenario 3: Processing document content
        doc_content = "[DOCUMENT]\r\nTitle: Test\r\n\r\nContent here"
        normalized_content = normalize_line_endings(doc_content)
        assert normalized_content == "[DOCUMENT]\nTitle: Test\n\nContent here"


@pytest.mark.parametrize("input_filename,expected", [
    ("normal.txt", "normal.txt"),
    ("../../../etc/passwd", "......etcpasswd"),
    ("file with spaces.pdf", "file with spaces.pdf"),
    ("", ""),
    (".hidden", ".hidden"),
    ("file<>:\"|?*.txt", "file.txt"),
])
def test_sanitize_filename_parametrized(input_filename: str, expected: str) -> None:
    """Parametrized tests for sanitize_filename function."""
    assert sanitize_filename(input_filename) == expected


@pytest.mark.parametrize("input_text,expected", [
    ("normal text", "normal text"),
    ("line1\nline2", "line1line2"),
    ("line1\r\nline2", "line1line2"),
    ("line1\rline2", "line1line2"),
    ("mixed\nline\r\nendings\r", "mixedlineendings"),
])
def test_sanitize_for_logging_parametrized(input_text: str, expected: str) -> None:
    """Parametrized tests for sanitize_for_logging function."""
    assert sanitize_for_logging(input_text) == expected


@pytest.mark.parametrize("input_content,expected", [
    ("unix\nlines", "unix\nlines"),
    ("windows\r\nlines", "windows\nlines"),
    ("mac\rlines", "mac\nlines"),
    ("mixed\nwin\r\nmac\rends", "mixed\nwin\nmac\nends"),
])
def test_normalize_line_endings_parametrized(input_content: str, expected: str) -> None:
    """Parametrized tests for normalize_line_endings function."""
    assert normalize_line_endings(input_content) == expected
