import time

from rich.console import Console
from rich.panel import Panel

from copium_loop.ui.pillar import MatrixPillar


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


def test_matrix_pillar_time_suffix():
    """Test time suffix rendering in MatrixPillar."""
    pillar = MatrixPillar("Coder")

    # Active
    pillar.start_time = time.time() - 65  # 1m 5s
    pillar.status = "active"
    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "1m 5s" in output

    # Success with completion time
    pillar.status = "success"
    pillar.completion_time = time.time()
    pillar.duration = 65
    panel = pillar.render()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "1m 5s" in output
    assert "@" in output  # Time of completion


def test_pillar_status_constants_are_frozensets():
    """Verify that status constants are frozensets as requested in PR review."""
    assert isinstance(MatrixPillar.COMPLETION_STATUSES, frozenset)
    assert isinstance(MatrixPillar.SUCCESS_STATUSES, frozenset)
    assert isinstance(MatrixPillar.FAILURE_STATUSES, frozenset)


def test_matrix_pillar_journaler_completion_status():
    """Test that journaler statuses (journaled, no_lesson) correctly trigger completion metrics."""
    pillar = MatrixPillar("Journaler")

    # Start active
    timestamp_start = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp_start)
    assert pillar.status == "active"
    assert pillar.start_time is not None

    # Set to 'journaled' after 10 seconds
    timestamp_end = "2026-01-25T12:00:10"
    pillar.set_status("journaled", timestamp_end)

    assert pillar.status == "journaled"
    assert pillar.duration == 10.0
    assert pillar.completion_time is not None

    # Render check
    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    # Should contain duration and completion timestamp
    assert "10s" in output
    assert "@" in output


def test_matrix_pillar_journaler_no_lesson_completion_status():
    """Test that 'no_lesson' status also triggers completion metrics."""
    pillar = MatrixPillar("Journaler")

    timestamp_start = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp_start)

    timestamp_end = "2026-01-25T12:00:05"
    pillar.set_status("no_lesson", timestamp_end)

    assert pillar.status == "no_lesson"
    assert pillar.duration == 5.0
    assert pillar.completion_time is not None

    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    assert "5s" in output
    assert "@" in output


def test_matrix_pillar_title_pill_shape():
    """Verify that get_title_text returns a pill-shaped title for active/success/failure statuses."""
    pillar = MatrixPillar("Coder")

    # Active
    pillar.status = "active"
    title = pillar.get_title_text()
    plain = title.plain
    assert "◖" in plain
    assert "◗" in plain
    assert " ▶ CODER " in plain
    # Verify colors (roughly, by checking if spans exist)
    assert len(title.spans) > 0

    # Success
    pillar.status = "success"
    title = pillar.get_title_text()
    plain = title.plain
    assert "◖" in plain
    assert "◗" in plain
    assert " ✔ CODER " in plain

    # Failure
    pillar.status = "failed"
    title = pillar.get_title_text()
    plain = title.plain
    assert "◖" in plain
    assert "◗" in plain
    assert " ✘ CODER " in plain

    # Idle (should NOT have pills)
    pillar.status = "idle"
    title = pillar.get_title_text()
    plain = title.plain
    assert "◖" not in plain
    assert "◗" not in plain
    assert "○ CODER" in plain
