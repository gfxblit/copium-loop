import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add src to sys.path to ensure local package is used during tests
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


@pytest.fixture(autouse=True)
def mock_telemetry_environment(monkeypatch, tmp_path):
    """
    Automatically patch the Telemetry class to use a temporary directory
    for logs, avoiding PermissionError during tests.
    """
    from copium_loop import telemetry

    def mock_init(self, session_id):
        self.session_id = session_id
        self.log_dir = tmp_path / ".copium" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{session_id}.jsonl"

    monkeypatch.setattr(telemetry.Telemetry, "__init__", mock_init)
    monkeypatch.setattr(telemetry, "_telemetry_instance", None)


@pytest.fixture
def workflow_manager_factory():
    """
    Fixture factory for creating WorkflowManager instances with optional
    start_node and verbose settings.
    """
    from copium_loop.copium_loop import WorkflowManager

    def _factory(start_node=None, verbose=False):
        return WorkflowManager(start_node=start_node, verbose=verbose)

    return _factory


@pytest.fixture
def mock_run_command():
    """
    Fixture to mock copium_loop.copium_loop.run_command.
    """
    with patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_verify_environment():
    """Fixture to mock WorkflowManager.verify_environment."""
    with patch("copium_loop.copium_loop.WorkflowManager.verify_environment", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def mock_get_telemetry():
    """Fixture to mock get_telemetry."""
    with patch("copium_loop.copium_loop.get_telemetry") as mock:
        yield mock

@pytest.fixture
def mock_create_graph():
    """Fixture to mock create_graph."""
    with patch("copium_loop.copium_loop.create_graph") as mock:
        yield mock

@pytest.fixture
def mock_get_head():
    """Fixture to mock get_head."""
    with patch("copium_loop.copium_loop.get_head", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def mock_get_test_command():
    """Fixture to mock get_test_command."""
    with patch("copium_loop.copium_loop.get_test_command") as mock:
        yield mock

@pytest.fixture
def mock_os_path_exists():
    """Fixture to mock os.path.exists."""
    with patch("os.path.exists") as mock:
        yield mock

@pytest.fixture
def mock_notify():
    """Fixture to mock copium_loop.copium_loop.notify."""
    with patch("copium_loop.copium_loop.notify", new_callable=AsyncMock) as mock:
        yield mock


