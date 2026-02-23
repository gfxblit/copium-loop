import os

from copium_loop.ui.manager import SessionManager


def test_manager_max_sessions_limit(tmp_path):
    """Verify that SessionManager respects max_sessions using the new heapq logic."""
    max_sessions = 5
    mgr = SessionManager(tmp_path, max_sessions=max_sessions)

    # Create 10 session files with different mtimes
    # We want the 5 most recent ones.
    # mtime: s0=100, s1=101, ..., s9=109

    # We need to sleep or explicitly set mtime to ensure order
    # Because os.utime precision depends on OS.

    files = []
    for i in range(10):
        fname = f"s{i}.jsonl"
        fpath = tmp_path / fname
        fpath.touch()
        # Set mtime explicitly
        os.utime(fpath, (1000 + i, 1000 + i))
        files.append(fpath)

    mgr.update_from_logs()

    # Should only have 5 sessions
    assert len(mgr.sessions) == 5

    # Should have s5, s6, s7, s8, s9 (the 5 most recent)
    expected_ids = {f"s{i}" for i in range(5, 10)}
    assert set(mgr.sessions.keys()) == expected_ids


def test_manager_heapq_vs_sort_correctness(tmp_path):
    """Verify that heapq implementation produces same result as sort."""
    mgr = SessionManager(tmp_path, max_sessions=10)

    # Create 20 files mixed up
    for i in range(20):
        fpath = tmp_path / f"session_{i}.jsonl"
        fpath.touch()
        # Random mtimes or just sequential
        os.utime(fpath, (1000 + i, 1000 + i))

    # Run update
    mgr.update_from_logs()

    assert len(mgr.sessions) == 10
    # Should be session_10 to session_19
    expected = {f"session_{i}" for i in range(10, 20)}
    assert set(mgr.sessions.keys()) == expected
