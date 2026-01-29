import time
from copium_loop.ui.pillar import MatrixPillar

def test_pillar_set_status_invalid_timestamp():
    """Test that invalid timestamps in set_status are handled gracefully."""
    p = MatrixPillar("Coder")
    p.set_status("active", "invalid-timestamp")
    assert p.status == "active"
    assert p.start_time is None

def test_pillar_render_duration_seconds():
    """Test that seconds duration is rendered correctly."""
    p = MatrixPillar("Coder")
    p.start_time = time.time() - 30
    p.status = "active"
    panel = p.render()
    # Should show [30s] (or slightly more/less depending on execution time, so we check for 's]')
    assert "s]" in str(panel.title)

def test_pillar_render_duration_minutes_exact():
    """Test that exact minutes duration is rendered correctly."""
    p = MatrixPillar("Coder")
    p.start_time = time.time() - 120
    p.status = "active"
    panel = p.render()
    # Should show [2m]
    assert "[2m]" in str(panel.title)

def test_pillar_render_error_status():
    """Test that error status is rendered correctly."""
    p = MatrixPillar("Coder")
    p.status = "error"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"

def test_pillar_render_rejected_status():
    """Test that rejected status is rendered correctly."""
    p = MatrixPillar("Reviewer")
    p.status = "rejected"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"

def test_pillar_render_failed_status():
    """Test that failed status is rendered correctly."""
    p = MatrixPillar("Tester")
    p.status = "failed"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"

def test_pillar_render_pr_failed_status():
    """Test that pr_failed status is rendered correctly."""
    p = MatrixPillar("PR Creator")
    p.status = "pr_failed"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"

def test_pillar_render_idle_empty():
    """Test that idle empty pillar is rendered correctly."""
    p = MatrixPillar("Coder")
    p.status = "idle"
    panel = p.render()
    assert "○" in str(panel.title)
    assert panel.border_style == "grey37"
