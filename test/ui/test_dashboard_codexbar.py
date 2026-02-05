from unittest.mock import patch

from copium_loop.ui.dashboard import Dashboard


class TestDashboardCodexbar:
    def test_footer_with_codexbar_data(self):
        with patch("copium_loop.ui.dashboard.CodexbarClient") as MockClient:
            # Setup mock client
            mock_client_instance = MockClient.return_value
            mock_client_instance.get_usage.return_value = {
                "pro": 85,
                "flash": 40,
                "reset": "18:30",
            }

            dash = Dashboard()

            # Ensure the client was initialized
            assert dash.codexbar_client == mock_client_instance

            # Generate footer
            footer_panel = dash.make_footer()

            # Verify content
            # Rich Renderables are complex, but we can check the text content if we extract it
            # The footer text is constructed as a Text object

            # Panel.renderable is the Text object
            text_obj = footer_panel.renderable
            plain_text = text_obj.plain

            assert "PRO: 85%" in plain_text
            assert "FLASH: 40%" in plain_text
            assert "RESET: 18:30" in plain_text
            assert "CPU:" not in plain_text
            assert "MEM:" not in plain_text

    def test_footer_without_codexbar_data(self):
        with patch("copium_loop.ui.dashboard.CodexbarClient") as MockClient:
            # Setup mock client to return None
            mock_client_instance = MockClient.return_value
            mock_client_instance.get_usage.return_value = None

            dash = Dashboard()

            footer_panel = dash.make_footer()
            text_obj = footer_panel.renderable
            plain_text = text_obj.plain

            assert "CPU:" in plain_text
            assert "MEM:" in plain_text
            assert "PRO:" not in plain_text
