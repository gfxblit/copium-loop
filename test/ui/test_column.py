import time

from rich.console import Console

from copium_loop.ui.column import SessionColumn


def test_session_column_rendering():
    """Test that SessionColumn renders its pillars."""
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
    assert "ARCHITECT" in output
    assert "coding..." in output


def test_session_column_no_number_hints():
    """Ensure that SessionColumn does not render a number hint in the title."""
    session = SessionColumn("test_session")

    # Render without index (it's removed from signature, but we check if it's there by default)
    layout = session.render(column_width=40)

    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()

    # We want to ensure no bracketed numbers like "[1]" or "[2]" are in the title area
    import re

    assert not re.search(r"\[\d+\]", output)
    assert "test_session" in output


def test_session_column_last_updated():
    """Verify SessionColumn.last_updated calculates the maximum last_update across pillars."""
    session = SessionColumn("test_session")

    # Manually set last_update for pillars to old values
    now = time.time()
    for pillar in session.pillars.values():
        pillar.last_update = now - 500

    session.pillars["coder"].last_update = now - 100
    session.pillars["tester"].last_update = now - 50
    session.pillars["architect"].last_update = now - 75
    session.pillars["reviewer"].last_update = now - 150
    session.pillars["pr_creator"].last_update = now - 200

    assert session.last_updated == now - 50

    # Update one pillar
    session.pillars["reviewer"].last_update = now + 10
    assert session.last_updated == now + 10


def test_session_column_status_banners():
    """Test workflow status banners in SessionColumn."""
    s = SessionColumn("test")

    # Success
    s.workflow_status = "success"
    layout = s.render()
    console = Console()
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "SUCCESS" in output

    # Failed
    s = SessionColumn("test_fail")
    s.workflow_status = "failed"
    layout = s.render()
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "FAILED" in output
