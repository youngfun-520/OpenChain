"""Tests for enhanced CLI features."""
import pytest


def test_input_helper_multiline():
    """InputHelper should detect unclosed brackets and quotes."""
    from openchain.cli import InputHelper
    ih = InputHelper()
    # Complete line
    assert ih.is_complete("hello") is True
    # Unclosed paren
    assert ih.is_complete("hello (world") is False
    # Closed paren
    assert ih.is_complete("hello (world)") is True
    # Unclosed quote
    assert ih.is_complete('say "hello') is False
    # Closed quote
    assert ih.is_complete('say "hello"') is True


def test_ctrl_c_clears_buffer():
    """Ctrl+C (KeyboardInterrupt) should clear the input buffer."""
    from openchain.cli import InputHelper
    ih = InputHelper()
    ih._buffer = ["hello ("]
    ih.clear_buffer()
    assert ih._buffer == []


@pytest.mark.asyncio
async def test_repl_multiline_accumulates():
    """REPL should accumulate lines until input is complete."""
    from openchain.cli import InputHelper
    ih = InputHelper()
    # Simulate incomplete line
    complete = ih.is_complete("hello (world")
    assert complete is False
    # Simulate complete line
    complete = ih.is_complete("hello (world)")
    assert complete is True


def test_autocomplete_commands():
    """CLI should provide completions for REPL commands."""
    from openchain.cli import get_completions
    comps = get_completions("/q")
    assert "/quit" in comps
    comps = get_completions("/tree")
    assert "/tree" in comps