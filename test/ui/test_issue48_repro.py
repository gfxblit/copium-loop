from rich.console import Console

from copium_loop.ui.pillar import MatrixPillar


def test_issue48_journaler_completion_status():
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


def test_issue48_journaler_no_lesson_completion_status():
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
