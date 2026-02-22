import pytest
from rich.console import Console
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class SessionWidgetMockApp(App):
    def __init__(self, column):
        super().__init__()
        self.session_column = column

    def compose(self) -> ComposeResult:
        yield SessionWidget(self.session_column)


def test_session_column_display_name_logic():
    # Regular case
    col = SessionColumn("owner/repo/branch")
    # This will fail initially because the property doesn't exist
    try:
        assert col.display_name == "repo/branch"
    except AttributeError:
        pytest.fail("SessionColumn does not have display_name property")

    # No slash case
    col = SessionColumn("branch-only")
    assert col.display_name == "branch-only"

    # One slash case
    col = SessionColumn("owner/branch")
    assert col.display_name == "branch"


class MockSessionColumn(SessionColumn):
    @property
    def display_name(self) -> str:
        return "MOCKED_DISPLAY_NAME"


def test_session_column_render_uses_display_name():
    col = MockSessionColumn("real/id")
    # We expect render() to call self.display_name which returns "MOCKED_DISPLAY_NAME"
    layout = col.render(column_width=40)

    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()

    # This will fail initially because render uses self.session_id directly
    if "MOCKED_DISPLAY_NAME" not in output:
        pytest.fail(
            f"SessionColumn.render did not use display_name property. Output: {output}"
        )


@pytest.mark.asyncio
async def test_session_widget_uses_display_name():
    col = MockSessionColumn("real/id")
    app = SessionWidgetMockApp(col)

    async with app.run_test():
        widget = app.query_one(SessionWidget)
        await widget.refresh_ui()

        header = widget.query_one(f"#header-{widget.safe_id}", Static)
        rendered = str(header.render())

        # This will fail initially because widget uses col.session_id directly
        if "MOCKED_DISPLAY_NAME" not in rendered:
            pytest.fail(
                f"SessionWidget did not use session_column.display_name. Rendered: {rendered}"
            )
