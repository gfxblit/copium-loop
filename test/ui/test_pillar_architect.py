from rich.console import Console

from copium_loop.ui.pillar import MatrixPillar


def test_matrix_pillar_architect_statuses():
    """Test that architect statuses (ok, refactor) correctly trigger completion metrics and styles."""

    # Test 'ok' status (Success)
    pillar_ok = MatrixPillar("Architect")
    timestamp_start = "2026-02-03T10:00:00"
    pillar_ok.set_status("active", timestamp_start)

    timestamp_end_ok = "2026-02-03T10:00:10"
    pillar_ok.set_status("ok", timestamp_end_ok)

    assert pillar_ok.status == "ok"
    assert pillar_ok.duration == 10.0
    assert pillar_ok.completion_time is not None

    panel_ok = pillar_ok.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel_ok)
    output_ok = capture.get()

    # Should contain checkmark (visualized as cyan in true color, but we check text/structure)
    # The render method uses "✔" for success
    assert "✔" in output_ok
    assert "10s" in output_ok
    assert "@" in output_ok

    # Test 'refactor' status (Failure)
    pillar_refactor = MatrixPillar("Architect")
    pillar_refactor.set_status("active", timestamp_start)

    timestamp_end_refactor = "2026-02-03T10:00:15"
    pillar_refactor.set_status("refactor", timestamp_end_refactor)

    assert pillar_refactor.status == "refactor"
    assert pillar_refactor.duration == 15.0
    assert pillar_refactor.completion_time is not None

    panel_refactor = pillar_refactor.render()
    with console.capture() as capture:
        console.print(panel_refactor)
    output_refactor = capture.get()

    # The render method uses "✘" for failure
    assert "✘" in output_refactor
    assert "15s" in output_refactor
    assert "@" in output_refactor
