from rich.console import Console
from copium_loop.ui.renderable import TailRenderable

def test_tail_renderable_basic():
    """Test that TailRenderable renders the last N lines."""
    buffer = ["line 1", "line 2", "line 3", "line 4", "line 5"]
    # We want to fit 3 lines
    renderable = TailRenderable(buffer, status="idle")

    console = Console(width=20, height=3)
    # Mocking options or similar might be needed if TailRenderable uses it
    # For now, let's just see if it handles height
    with console.capture() as capture:
        console.print(renderable)

    output = capture.get()
    # If height is 3, it should show line 3, 4, 5
    assert "line 3" in output
    assert "line 4" in output
    assert "line 5" in output
    assert "line 1" not in output
    assert "line 2" not in output

def test_tail_renderable_wrapping():
    """Test that TailRenderable handles line wrapping when calculating the tail."""
    # Line that will wrap into 2 lines if width is small
    buffer = ["short 1", "this is a very long line that should wrap", "short 2"]
    # width=20, "  this is a very long line that should wrap" is ~44 chars
    # It should wrap into 3 lines:
    # "  this is a very"
    # "long line that"
    # "should wrap"

    # height=3 should show "short 2" and the last 2 lines of the wrapped line
    # Wait, height=3, and we have:
    # L1: "short 2" (1 line)
    # L2: "should wrap" (wrapped part of long line)
    # L3: "long line that" (wrapped part of long line)

    renderable = TailRenderable(buffer, status="idle")
    console = Console(width=20, height=3)
    with console.capture() as capture:
        console.print(renderable)

    output = capture.get()
    assert "short 2" in output
    assert "should wrap" in output
    assert "long line that" in output
    assert "short 1" not in output
    assert "this is a very" not in output

def test_tail_renderable_empty():
    """Test that TailRenderable handles an empty buffer."""
    renderable = TailRenderable([], status="idle")
    console = Console()
    with console.capture() as capture:
        console.print(renderable)
    output = capture.get()
    assert output == ""

def test_tail_renderable_styling():
    """Test that TailRenderable applies correct styles based on recency and status."""
    buffer = [f"line {i}" for i in range(15)]
    # newest is line 14

    # Test active status (white with > prefix)
    renderable_active = TailRenderable(buffer, status="active")
    console = Console(width=20)
    with console.capture() as capture:
        console.print(renderable_active)
    output_active = capture.get()
    assert "> line 14" in output_active

    # Test idle status (should ALWAYS have > prefix for newest line now)
    renderable_idle = TailRenderable(buffer, status="idle")
    with console.capture() as capture:
        console.print(renderable_idle)
    output_idle = capture.get()
    assert "> line 14" in output_idle
    assert "  line 14" not in output_idle

    # others should have "  "
    assert "  line 13" in output_active
    assert "  line 10" in output_active
    assert "  line 0" in output_active
