
import pytest
from unittest.mock import MagicMock
from pathlib import Path

@pytest.fixture(autouse=True)
def mock_telemetry_environment(monkeypatch, tmp_path):
    """
    Automatically patch the Telemetry class to use a temporary directory
    for logs, avoiding PermissionError during tests.
    """
    # Define a MockTelemetry that behaves like the real one but uses tmp_path
    # We can just monkeypatch the log_dir in __init__?
    
    # Actually, simpler to patch the `Path.home()` used in Telemetry.__init__
    # But that might have side effects.
    
    # Let's patch the Telemetry class directly.
    from copium_loop import telemetry
    
    original_init = telemetry.Telemetry.__init__
    
    def mock_init(self, session_id):
        self.session_id = session_id
        self.log_dir = tmp_path / ".copium" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{session_id}.jsonl"
        
    monkeypatch.setattr(telemetry.Telemetry, "__init__", mock_init)
    
    # Ensure the singleton is reset so get_telemetry creates a new one with our mock init
    monkeypatch.setattr(telemetry, "_telemetry_instance", None)
