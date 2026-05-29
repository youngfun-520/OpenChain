"""Tests for aiosqlite event loop cleanup."""
import pytest
import asyncio
import gc


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    """Ensure any lingering database connections are closed after each test."""
    yield
    # Allow background tasks to complete
    await asyncio.sleep(0.01)
    gc.collect()


@pytest.mark.asyncio
async def test_database_context_manager_no_warning():
    """Database context manager should not produce event loop warnings."""
    from openchain.db import Database
    import warnings
    import io
    import sys

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async with Database(":memory:") as db:
            await db.initialize()
            await db.execute("CREATE TABLE test (id INTEGER)")
            await db.commit()

        # Wait for background thread to clean up
        await asyncio.sleep(0.05)
        gc.collect()

        # Filter for event loop warnings
        event_loop_warnings = [
            x for x in w
            if "event loop" in str(x.message).lower() or "runtimeerror" in str(x.message).lower()
        ]

        # This test passes if no event loop warnings (the goal)
        assert len(event_loop_warnings) == 0, f"Event loop warnings found: {[str(x.message) for x in event_loop_warnings]}"


@pytest.mark.asyncio
async def test_session_manager_no_warning():
    """SessionManager context manager should not produce event loop warnings."""
    from openchain.session import SessionManager
    import warnings
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            async with SessionManager(db_path) as sm:
                await sm.initialize()
                await sm.create_session(workspace=tmpdir)

            await asyncio.sleep(0.05)
            gc.collect()

            event_loop_warnings = [
                x for x in w
                if "event loop" in str(x.message).lower() or "runtimeerror" in str(x.message).lower()
            ]
            assert len(event_loop_warnings) == 0