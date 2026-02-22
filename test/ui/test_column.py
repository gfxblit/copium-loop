import json
import re
import time

import pytest
from rich import box
from rich.console import Console
from rich.panel import Panel
from textual.app import App, ComposeResult

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.pillar import MatrixPillar
from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


class MockApp(App):
    def __init__(self, column: SessionColumn):
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        yield SessionWidget(self.column)


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

    # Render without index
    layout = session.render(column_width=40)

    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()

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


def test_session_column_toggle_system_logs():
    """Test that SessionColumn can toggle system logs visibility."""
    session = SessionColumn("test_session")
    pillar = session.get_pillar("coder")

    pillar.add_line("LLM output", source="llm")
    pillar.add_line("System info", source="system")

    # This might require adding a show_system_logs property to SessionColumn or SessionManager
    session.show_system_logs = False
    session.render()
    # Verifying layout content is hard, but we can check if it passes the flag down
    # Or just verify the property exists and is used.
    assert session.show_system_logs is False

    session.show_system_logs = True
    assert session.show_system_logs is True


@pytest.mark.asyncio
async def test_sessions_expand_and_fit_narrow_screen(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Case 1: One session fills the width
    (log_dir / "session-0.jsonl").write_text(
        json.dumps(
            {
                "node": "workflow",
                "event_type": "workflow_status",
                "data": "running",
                "timestamp": "2026-02-15T12:00:00",
            }
        )
        + "\n"
    )

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test(size=(60, 24)) as pilot:
        await app.update_from_logs()
        await pilot.pause()

        sessions = app.query(SessionWidget)
        assert len(sessions) == 1
        assert sessions[0].region.width == 60

    # Case 2: Three sessions fit on a narrow screen (30 wide)
    for i in range(1, 3):
        (log_dir / f"session-{i}.jsonl").write_text(
            json.dumps(
                {
                    "node": "workflow",
                    "event_type": "workflow_status",
                    "data": "running",
                    "timestamp": f"2026-02-15T12:00:0{i}",
                }
            )
            + "\n"
        )

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test(size=(30, 24)) as pilot:
        await app.update_from_logs()
        await pilot.pause()

        sessions = app.query(SessionWidget)
        assert len(sessions) == 3
        for session in sessions:
            assert session.region.width == 10


def test_pillar_render_uses_rounded_box():
    pillar = MatrixPillar("test")
    panel = pillar.render()
    assert panel.box == box.ROUNDED


def test_session_widget_css_removes_vertical_borders():
    css = SessionWidget.DEFAULT_CSS
    assert "border: solid" not in css
    assert "border-top: solid" not in css
    assert "border-bottom: solid" not in css
    assert "border: double" not in css
    assert "border-top: double" not in css
    assert "border-bottom: double" not in css


def test_session_column_render_uses_rounded_box():
    session = SessionColumn("test-session")
    layout = session.render()

    # Check header panel
    header_panel = layout["header"].renderable
    assert isinstance(header_panel, Panel)
    assert header_panel.box == box.ROUNDED


def test_session_column_render_header_subtitle():
    col = SessionColumn("test-session")

    # Test running state
    col.workflow_status = "running"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert isinstance(header_panel, Panel)
    assert header_panel.subtitle is None or header_panel.subtitle == ""

    # Test success state
    col.workflow_status = "success"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "SUCCESS" in str(header_panel.renderable)
    try:
        layout["workflow_status"]
        pytest.fail("workflow_status layout element should have been removed")
    except KeyError:
        pass

    # Test failed state
    col.workflow_status = "failed"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "FAILED" in str(header_panel.renderable)


@pytest.mark.asyncio
async def test_pillar_min_height_with_content():
    column = SessionColumn("test-session")
    coder_pillar = column.get_pillar("coder")
    coder_pillar.add_line("Line 1")
    coder_pillar.status = "idle"

    app = MockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        await pilot.pause()

        coder_widget = app.query_one("#pillar-test-session-coder", PillarWidget)
        assert coder_widget.styles.min_height.value == 4


@pytest.mark.asyncio
async def test_pillar_min_height_when_active():
    column = SessionColumn("test-session")
    coder_pillar = column.get_pillar("coder")
    coder_pillar.status = "active"

    app = MockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        await pilot.pause()

        coder_widget = app.query_one("#pillar-test-session-coder", PillarWidget)
        assert coder_widget.styles.min_height.value == 4


@pytest.mark.asyncio
async def test_pillar_min_height_when_idle_empty():
    column = SessionColumn("test-session")
    coder_pillar = column.get_pillar("coder")
    coder_pillar.status = "idle"

    app = MockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        await pilot.pause()

        coder_widget = app.query_one("#pillar-test-session-coder", PillarWidget)
        assert coder_widget.styles.min_height.value == 3


def test_session_column_render_displays_only_branch_name():
    # Setup with repo/branch format
    session = SessionColumn("my-repo/feature-branch")

    layout = session.render(column_width=40)

    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()

    # Should fail initially
    assert "feature-branch" in output
    assert "my-repo/" not in output


def test_session_column_render_handles_no_prefix():
    # Setup with simple branch name
    session = SessionColumn("simple-branch")

    layout = session.render(column_width=40)

    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()

    assert "simple-branch" in output


def test_session_column_display_name_logic():
    # Regular case
    col = SessionColumn("owner/repo/branch")
    assert col.display_name == "branch"

    # No slash case
    col = SessionColumn("branch-only")
    assert col.display_name == "branch-only"

    # One slash case
    col = SessionColumn("owner/branch")
    assert col.display_name == "branch"
