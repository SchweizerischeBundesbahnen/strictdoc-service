"""Tests for uvloop compatibility.

uvloop is required for optimal async performance with uvicorn.
These tests verify uvloop is properly installed and functional.
"""

import sys

import pytest


def test_uvloop_must_be_available() -> None:
    """Test that uvloop is available and can be imported.

    uvloop is a hard requirement because uvicorn[standard] depends on it
    for better async performance (~2-4x faster than standard asyncio).
    """
    python_version = sys.version_info

    try:
        import uvloop

        assert uvloop.__version__ is not None, "uvloop version should be available"
        print(f"✅ uvloop {uvloop.__version__} works on Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    except ImportError as e:
        pytest.fail(
            f"❌ Failed to import uvloop on Python {python_version.major}.{python_version.minor}\n\n"
            f"Error: {e}\n\n"
            f"Possible causes:\n"
            f"- Missing C compiler (needed for source builds on some platforms)\n"
            f"- Incompatible Python version\n"
            f"- Installation problems\n\n"
            f"Check that uvicorn[standard] is properly installed."
        )


def test_uvloop_event_loop_functionality() -> None:
    """Test that uvloop can create and run an event loop.

    Goes beyond import checking to verify uvloop functions at runtime.
    """
    import asyncio

    python_version = sys.version_info

    try:
        import uvloop

        # Use uvloop.run() which is the modern API (Python 3.12+)
        async def simple_task() -> str:
            await asyncio.sleep(0)
            return "uvloop works"

        result = uvloop.run(simple_task())
        assert result == "uvloop works", "uvloop event loop should execute async tasks"

        print(f"✅ uvloop event loop functional on Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    except Exception as e:
        pytest.fail(
            f"❌ uvloop event loop FAILED on Python {python_version.major}.{python_version.minor}\n\n"
            f"Error: {e}\n\n"
            f"uvloop imported successfully but failed to function as an event loop."
        )


def test_uvicorn_has_uvloop_extras() -> None:
    """Test that uvicorn was installed with [standard] extras including uvloop.

    If uvloop is not available, uvicorn falls back to the standard asyncio
    event loop, which works but is slower (~2-4x slower for async I/O).
    """
    try:
        import uvloop  # noqa: F401
        has_uvloop = True
    except ImportError:
        has_uvloop = False

    assert has_uvloop, (
        "uvloop is not available. This means either:\n"
        "1. uvicorn was installed without [standard] extras, OR\n"
        "2. uvloop failed to install/compile\n\n"
        "Expected dependency: uvicorn[standard] which includes uvloop"
    )
