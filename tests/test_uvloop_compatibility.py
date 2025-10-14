"""Tests for uvloop compatibility."""

import asyncio
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


def test_uvloop_event_loop_functionality() -> None:
    """Test that uvloop can actually create and run an event loop.

    This test goes beyond import checking and verifies that uvloop can
    actually function as an event loop replacement. This catches issues
    where uvloop imports successfully but fails at runtime.

    Common failure scenarios:
    - Python 3.14 on some platforms: compiles but has runtime issues
    - Missing system dependencies
    - Incompatible asyncio changes
    """
    python_version = sys.version_info

    # Save the original event loop policy to restore after test
    original_policy = asyncio.get_event_loop_policy()

    try:
        import uvloop

        # Try to install uvloop as the event loop policy
        uvloop.install()

        # Create a new event loop to use uvloop (existing loop won't change)
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        # Verify uvloop is actually being used, not just asyncio
        assert "uvloop" in type(new_loop).__module__, (
            f"uvloop.install() did not activate uvloop. "
            f"Current event loop type: {type(new_loop).__module__}.{type(new_loop).__name__}"
        )

        # Create a simple async function to test the event loop
        async def simple_task():
            await asyncio.sleep(0)
            return "uvloop works"

        # Run a simple task with uvloop
        result = new_loop.run_until_complete(simple_task())

        assert result == "uvloop works", "uvloop event loop should execute async tasks"

        print(f"✅ uvloop event loop functional on Python {python_version.major}.{python_version.minor}.{python_version.micro}")

        # Clean up the loop
        new_loop.close()

    except Exception as e:
        error_msg = str(e)
        pytest.fail(
            f"❌ uvloop event loop FAILED on Python {python_version.major}.{python_version.minor}\n\n"
            f"Error: {error_msg}\n\n"
            f"uvloop imported successfully but failed to function as an event loop.\n"
            f"This indicates a runtime compatibility issue.\n\n"
            f"SOLUTIONS:\n"
            f"1. Check if your Python version is fully supported by uvloop\n"
            f"2. Downgrade to Python 3.13.x (recommended)\n"
            f"3. Remove uvloop by changing 'uvicorn[standard]' to 'uvicorn' in pyproject.toml\n\n"
            f"See: https://github.com/MagicStack/uvloop/issues/637"
        )
    finally:
        # Restore the original event loop policy to prevent side effects
        asyncio.set_event_loop_policy(original_policy)


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
