from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.pillar import MatrixPillar


class PillTestApp(App):
    """Test app to render MatrixPillar titles (pills)."""

    CSS = """
    Static {
        margin: 1 2;
        padding: 1;
        height: 6;
        border: round;
        border-title-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        # 1. Active Status
        pillar_active = MatrixPillar("ACTIVE_CODER")
        pillar_active.status = "active"
        w_active = Static("Active Status: Should be neon green pill with black text")
        w_active.border_title = pillar_active.get_title_text()
        w_active.styles.border = ("round", pillar_active.get_status_color())
        yield w_active

        # 2. Success Status
        pillar_success = MatrixPillar("SUCCESS_CODER")
        pillar_success.status = "success"
        w_success = Static("Success Status: Should be cyan pill with black text")
        w_success.border_title = pillar_success.get_title_text()
        w_success.styles.border = ("round", pillar_success.get_status_color())
        yield w_success

        # 3. Failed Status
        pillar_failed = MatrixPillar("FAILED_CODER")
        pillar_failed.status = "failed"
        w_failed = Static("Failed Status: Should be red pill with white text")
        w_failed.border_title = pillar_failed.get_title_text()
        w_failed.styles.border = ("round", pillar_failed.get_status_color())
        yield w_failed

        # 4. Idle Status
        pillar_idle = MatrixPillar("IDLE_CODER")
        pillar_idle.status = "idle"
        w_idle = Static("Idle Status: Should be grey circle (no pill)")
        w_idle.border_title = pillar_idle.get_title_text()
        w_idle.styles.border = ("round", pillar_idle.get_status_color())
        yield w_idle

    def on_mount(self) -> None:
        self.call_after_refresh(self.exit)


if __name__ == "__main__":
    app = PillTestApp()
    app.run()
