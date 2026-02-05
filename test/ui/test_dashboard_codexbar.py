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

            # Updated for Issue #60: Show percent remaining (100 - usage)
            # 100 - 85 = 15
            assert "PRO LEFT: 15.0%" in plain_text
            # 100 - 40 = 60
            assert "FLASH LEFT: 60.0%" in plain_text
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
            assert "PRO LEFT:" not in plain_text

    def test_dependency_injection(self):
        """Test that we can inject a custom client."""

        class DummyClient:
            def get_usage(self):
                return {"pro": 10, "flash": 10, "reset": "00:00"}

        my_client = DummyClient()
        dash = Dashboard(codexbar_client=my_client)

        # Verify injection worked
        assert dash.codexbar_client is my_client

        # Verify it uses the injected client
        footer_panel = dash.make_footer()
        plain_text = footer_panel.renderable.plain

        # 100 - 10 = 90
        assert "PRO LEFT: 90.0%" in plain_text
