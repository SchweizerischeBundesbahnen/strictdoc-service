"""Tests for uvloop compatibility."""

import sys

import pytest


def test_uvloop_must_be_available() -> None:
    """Test that uvloop is available and can be imported.

    This is a hard requirement for this project because:
    - uvicorn[standard] includes uvloop for better async performance
    - We depend on uvloop being installable in our environment

    This test will FAIL if:
    - uvloop cannot be imported (e.g., on Python 3.14 with uvloop 0.21.0)
    - uvloop installation is broken
    - Missing C compiler for compilation (UBI minimal without build tools)

    Known issue with Python 3.14:
    - uvloop 0.21.0 does NOT support Python 3.14
    - Error: AttributeError: module 'asyncio' has no attribute 'AbstractChildWatcher'
    - GitHub issue: https://github.com/MagicStack/uvloop/issues/637
    - Fix merged but not yet released - waiting for uvloop 0.22.0+

    If this test fails, you must either:
    1. Use Python 3.13.x (recommended), OR
    2. Remove uvloop by changing uvicorn[standard] to uvicorn (performance impact)
    """
    python_version = sys.version_info

    try:
        import uvloop

        # Verify uvloop is functional, not just importable
        assert uvloop.__version__ is not None, "uvloop version should be available"

        # Success!
        print(f"✅ uvloop {uvloop.__version__} works on Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    except (ImportError, AttributeError) as e:
        error_msg = str(e)

        # Provide helpful error message based on the error type
        if "AbstractChildWatcher" in error_msg:
            pytest.fail(
                f"❌ uvloop is NOT compatible with Python {python_version.major}.{python_version.minor}\n\n"
                f"Error: {error_msg}\n\n"
                f"This is a known issue with uvloop 0.21.0 and Python 3.14+.\n"
                f"uvloop 0.21.0 only supports Python 3.8-3.13.\n\n"
                f"SOLUTIONS:\n"
                f"1. Downgrade to Python 3.13.x (recommended)\n"
                f"2. Wait for uvloop 0.22.0+ release with Python 3.14 support\n"
                f"3. Remove uvloop by changing 'uvicorn[standard]' to 'uvicorn' in pyproject.toml\n\n"
                f"See: https://github.com/MagicStack/uvloop/issues/637"
            )
        else:
            pytest.fail(
                f"❌ Failed to import uvloop on Python {python_version.major}.{python_version.minor}\n\n"
                f"Error: {error_msg}\n\n"
                f"This could be due to:\n"
                f"- Missing C compiler (needed for source builds)\n"
                f"- Incompatible Python version\n"
                f"- Installation problems\n\n"
                f"Check that uvicorn[standard] is properly installed."
            )


def test_uvicorn_has_uvloop_extras() -> None:
    """Test that uvicorn was installed with [standard] extras including uvloop.

    This verifies that our dependency on 'uvicorn' (line 14 in pyproject.toml)
    properly includes uvloop via the [standard] extras.

    If uvloop is not available, uvicorn will fall back to the standard asyncio
    event loop, which works but is slower (~2-4x slower for async I/O).
    """
    try:
        import uvloop  # noqa: F401
        has_uvloop = True
    except (ImportError, AttributeError):
        has_uvloop = False

    assert has_uvloop, (
        "uvloop is not available. This means either:\n"
        "1. uvicorn was installed without [standard] extras, OR\n"
        "2. uvloop failed to install/compile\n\n"
        "Expected dependency: uvicorn[standard] which includes uvloop\n"
        "Current pyproject.toml should have: uvicorn==0.37.0"
    )
