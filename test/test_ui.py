from rich.console import Console
from rich.panel import Panel

from copium_loop.ui import MatrixPillar, TailRenderable


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

def test_tail_renderable_empty():
    """Test that TailRenderable handles an empty buffer."""
    renderable = TailRenderable([], status="idle")
    console = Console()
    with console.capture() as capture:
        console.print(renderable)
    output = capture.get()
    assert output == ""

def test_matrix_pillar_render_order():
    """Test that MatrixPillar renders logs in chronological order (oldest to newest)."""
    pillar = MatrixPillar("Coder")
    pillar.add_line("first")
    pillar.add_line("second")
    pillar.add_line("third")

    panel = pillar.render()
    assert isinstance(panel, Panel)

    # We need to verify the content of the panel
    console = Console(width=20)
    with console.capture() as capture:
        console.print(panel)

    output = capture.get()
    # Chronological order: first, second, third (top to bottom)
    first_idx = output.find("first")
    second_idx = output.find("second")
    third_idx = output.find("third")

    assert first_idx != -1
    assert second_idx != -1
    assert third_idx != -1
    assert first_idx < second_idx < third_idx

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

    # Test idle status (should NOT have > prefix for newest line)
    renderable_idle = TailRenderable(buffer, status="idle")
    with console.capture() as capture:
        console.print(renderable_idle)
    output_idle = capture.get()
    assert "> line 14" not in output_idle
    assert "  line 14" in output_idle

    # others should have "  "
    assert "  line 13" in output_active
    assert "  line 10" in output_active
    assert "  line 0" in output_active

def test_matrix_pillar_status_and_duration():
    """Test that MatrixPillar correctly tracks status and duration."""
    pillar = MatrixPillar("Coder")

    # Initial state
    assert pillar.status == "idle"
    assert pillar.duration is None

    # Set to active
    timestamp = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp)
    assert pillar.status == "active"

    # Set to success after 10 seconds
    timestamp_end = "2026-01-25T12:00:10"
    pillar.set_status("success", timestamp_end)
    assert pillar.status == "success"
    assert pillar.duration == 10.0
    assert pillar.completion_time is not None

def test_matrix_pillar_buffer_limit():
    """Test that MatrixPillar respects its max_buffer size."""
    pillar = MatrixPillar("Coder")
    pillar.max_buffer = 5

    for i in range(10):
        pillar.add_line(f"line {i}")

    assert len(pillar.buffer) == 5
    assert pillar.buffer[0] == "line 5"
    assert pillar.buffer[-1] == "line 9"

def test_session_column_rendering():
    """Test that SessionColumn renders its pillars."""
    from copium_loop.ui import SessionColumn
    session = SessionColumn("test_session")

    # Set some content and status
    session.pillars["coder"].add_line("coding...")
    session.pillars["coder"].set_status("active")

    layout = session.render(column_width=40)

    # Verify it renders to console without crashing
    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "test_session" in output
    assert "CODER" in output
    assert "coding..." in output

def test_dashboard_extract_tmux_session():
    """Test that Dashboard.extract_tmux_session correctly parses session IDs."""
    from copium_loop.ui import Dashboard
    dash = Dashboard()

    assert dash.extract_tmux_session("my_session") == "my_session"
    assert dash.extract_tmux_session("my_session_0") == "my_session"
    assert dash.extract_tmux_session("my_session_%1") == "my_session"
    assert dash.extract_tmux_session("session_12345678") is None
