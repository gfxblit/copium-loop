import re

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


class SessionWidgetMockApp(App):
    def __init__(self, column=None, index=0):
        super().__init__()
        self.session_column = column or SessionColumn("test-session")
        self.session_widget = None
        self.index = index

    def compose(self) -> ComposeResult:
        self.session_widget = SessionWidget(self.session_column, index=self.index)
        yield self.session_widget


@pytest.mark.asyncio
async def test_session_widget_contains_pillars():
    app = SessionWidgetMockApp()
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        assert session_widget.session_id == "test-session"

        # Manually trigger refresh to populate pillars
        await session_widget.refresh_ui()
        await pilot.pause()

        # Check if basic pillars are present
        pillars = session_widget.query(PillarWidget)
        assert len(pillars) >= 6

        coder_pillar = session_widget.query_one(
            "#pillar-test-session-coder", PillarWidget
        )
        assert coder_pillar.node_id == "coder"


@pytest.mark.asyncio
async def test_session_widget_status_merging():
    app = SessionWidgetMockApp()
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)

        # Success status
        session_widget.session_column.workflow_status = "success"
        await session_widget.refresh_ui()
        await pilot.pause()

        header = session_widget.query_one("#header-test-session", Static)
        assert "✓" in str(header.render())
        assert "test-session" in str(header.render())

        # Failed status
        session_widget.session_column.workflow_status = "failed"
        await session_widget.refresh_ui()
        await pilot.pause()

        header = session_widget.query_one("#header-test-session", Static)
        assert "⚠" in str(header.render())
        assert "test-session" in str(header.render())


@pytest.mark.asyncio
async def test_session_widget_header_status_extended():
    col = SessionColumn("test-session")
    app = SessionWidgetMockApp(col)
    async with app.run_test():
        widget = app.session_widget

        # Helper to get plain text from header content
        def get_plain_content(h):
            content = h.render()
            if not content:
                return ""
            s = str(content.plain) if hasattr(content, "plain") else str(content)
            return re.sub(r"\[.*?\]", "", s)

        # Test running state
        col.workflow_status = "running"
        await widget.refresh_ui()
        header = widget.query_one("#header-test-session", Static)
        assert "SUCCESS" not in get_plain_content(header)
        assert "FAILED" not in get_plain_content(header)
        assert header.styles.border.top[1].rgb == (255, 255, 0)  # yellow

        # Test success state
        col.workflow_status = "success"
        await widget.refresh_ui()
        assert "✓ SUCCESS" in get_plain_content(header)

        # Test failed state
        col.workflow_status = "failed"
        await widget.refresh_ui()
        assert "⚠ FAILED" in get_plain_content(header)
        assert header.styles.border.top[1].rgb == (255, 0, 0)  # red


@pytest.mark.asyncio
async def test_lean_nodes_weight_and_content():
    column = SessionColumn("test-session")

    # Setup 'tester' as a lean node with content and active status
    column.pillars["tester"].add_line("This should be suppressed")
    column.pillars["tester"].status = "active"

    # Setup 'coder' as a normal node with content and active status
    column.pillars["coder"].add_line("This should be visible")
    column.pillars["coder"].status = "active"

    app = SessionWidgetMockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.session_widget
        # Trigger UI refresh to apply styles
        await session_widget.refresh_ui()
        await pilot.pause()

        tester_widget = session_widget.query_one(
            "#pillar-test-session-tester", PillarWidget
        )
        coder_widget = session_widget.query_one(
            "#pillar-test-session-coder", PillarWidget
        )

        # Coder should have high weight because it's active and normal
        # 100 base + 2 per line * 1 line = 102
        assert coder_widget.styles.height.value == 102

        # Tester is lean and active, so it should have lower weight than coder
        # 50 base + 2 per line * 1 line = 52
        assert tester_widget.styles.height.value == 52


@pytest.mark.asyncio
async def test_session_widget_displays_only_branch_name():
    # Setup with repo/branch format
    col = SessionColumn("my-repo/feature-branch")
    app = SessionWidgetMockApp(col)

    async with app.run_test():
        widget = app.query_one(SessionWidget)

        # Initial check
        await widget.refresh_ui()
        header = widget.query_one(f"#header-{widget.safe_id}", Static)
        rendered = str(header.render())

        # Should fail initially as it will show full ID
        assert "feature-branch" in rendered
        assert "my-repo/" not in rendered


@pytest.mark.asyncio
async def test_session_widget_handles_no_prefix():
    # Setup with simple branch name
    col = SessionColumn("simple-branch")
    app = SessionWidgetMockApp(col)

    async with app.run_test():
        widget = app.query_one(SessionWidget)

        await widget.refresh_ui()
        header = widget.query_one(f"#header-{widget.safe_id}", Static)
        rendered = str(header.render())

        assert "simple-branch" in rendered


@pytest.mark.asyncio
async def test_session_widget_displays_index():
    col = SessionColumn("test-session")
    # Pass index=1
    app = SessionWidgetMockApp(col, index=1)
    async with app.run_test():
        widget = app.session_widget

        await widget.refresh_ui()
        header = widget.query_one(f"#header-{widget.safe_id}", Static)
        rendered = str(header.render())

        # We expect "[1]" to be in the header
        assert "[1]" in rendered


@pytest.mark.asyncio
async def test_session_widget_no_index_for_zero():
    col = SessionColumn("test-session")
    # Pass index=0
    app = SessionWidgetMockApp(col, index=0)
    async with app.run_test():
        widget = app.session_widget

        await widget.refresh_ui()
        header = widget.query_one(f"#header-{widget.safe_id}", Static)
        rendered = str(header.render())

        # We expect no "[0]" in the header
        assert "[0]" not in rendered
