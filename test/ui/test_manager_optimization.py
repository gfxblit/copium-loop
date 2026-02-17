from unittest.mock import MagicMock, mock_open, patch

import pytest
from src.copium_loop.ui.manager import SessionManager


@pytest.fixture
def mock_scandir():
    with patch("os.scandir") as mock:
        yield mock


@pytest.fixture
def mock_file_open():
    with patch(
        "builtins.open",
        mock_open(
            read_data='{"node": "test", "event_type": "status", "data": "active"}'
        ),
    ) as mock:
        yield mock


def test_update_from_logs_caching(mock_scandir, mock_file_open, tmp_path):
    # Setup
    manager = SessionManager(tmp_path)

    # Mock DirEntry
    entry1 = MagicMock()
    entry1.name = "session_1.jsonl"
    entry1.is_file.return_value = True
    entry1.path = str(tmp_path / "session_1.jsonl")

    # Configure stat
    stat1 = MagicMock()
    stat1.st_mtime = 1000.0
    stat1.st_size = 100
    entry1.stat.return_value = stat1

    # Mock scandir to return this entry
    mock_scandir.return_value.__enter__.return_value = [entry1]

    # First run: should open file
    # Mock SessionColumn instantiation inside manager
    with patch("src.copium_loop.ui.manager.SessionColumn"):
        updates = manager.update_from_logs()

    assert mock_file_open.call_count == 1
    assert len(updates) == 1
    assert updates[0]["session_id"] == "session_1"
    assert mock_file_open.call_count == 1
    assert manager.file_stats["session_1"] == (1000.0, 100)

    # Second run: same stats, should NOT open file
    mock_file_open.reset_mock()
    updates = manager.update_from_logs()

    assert len(updates) == 0  # No new updates reported
    assert mock_file_open.call_count == 0  # Optimization working!

    # Third run: changed stats, should open file
    stat2 = MagicMock()
    stat2.st_mtime = 1001.0
    stat2.st_size = 200
    entry1.stat.return_value = stat2  # Update return value for next call

    # Verify mock setup
    assert entry1.stat().st_mtime == 1001.0

    # Provide more data so reading from previous offset finds new content
    more_data = '{"node": "test", "event_type": "status", "data": "active"}\n{"node": "test", "event_type": "status", "data": "new"}'
    new_mock = mock_open(read_data=more_data)
    mock_file_open.side_effect = new_mock.side_effect
    mock_file_open.return_value = new_mock.return_value

    mock_file_open.reset_mock()
    with patch("src.copium_loop.ui.manager.SessionColumn"):
        updates = manager.update_from_logs()

    assert mock_file_open.call_count == 1
    # We don't check len(updates) here because mocking partial reads/seeks with mock_open is tricky
    # and we primarily want to verify that the file was opened (optimization logic).
    assert manager.file_stats["session_1"] == (1001.0, 200)


def test_stale_stats_cleanup(mock_scandir, tmp_path):
    manager = SessionManager(tmp_path)

    # Run 1: file exists
    entry1 = MagicMock()
    entry1.name = "session_1.jsonl"
    entry1.is_file.return_value = True
    entry1.stat.return_value.st_mtime = 1000
    entry1.stat.return_value.st_size = 100

    mock_scandir.return_value.__enter__.return_value = [entry1]

    with patch("src.copium_loop.ui.manager.SessionColumn"):
        manager.update_from_logs()

    assert "session_1" in manager.file_stats

    # Run 2: file gone
    mock_scandir.return_value.__enter__.return_value = []

    manager.update_from_logs()

    assert "session_1" not in manager.file_stats
