from datetime import datetime

from rich.text import Text

from copium_loop.ui.pillar import MatrixPillar


def test_matrix_pillar_title_and_subtitle():
    pillar = MatrixPillar("coder")

    # Test idle state
    title = pillar.get_title_text()
    subtitle = pillar.get_subtitle_text()
    assert isinstance(title, Text)
    assert title.plain == "○ CODER"
    assert subtitle.plain == ""

    # Test active state
    pillar.set_status("active", datetime.now().isoformat())
    title = pillar.get_title_text()
    assert title.plain == "▶ CODER"

    # Test success state
    pillar.set_status("success", datetime.now().isoformat())
    title = pillar.get_title_text()
    subtitle = pillar.get_subtitle_text()
    assert title.plain == "✔ CODER"
    assert "SUCCESS" in subtitle.plain
    assert "@" in subtitle.plain  # Should have completion time


def test_matrix_pillar_duration_in_subtitle():
    pillar = MatrixPillar("coder")
    start_time = datetime(2026, 2, 16, 10, 0, 0)
    end_time = datetime(2026, 2, 16, 10, 1, 5)  # 1m 5s duration

    pillar.set_status("active", start_time.isoformat())
    pillar.set_status("success", end_time.isoformat())

    subtitle = pillar.get_subtitle_text()
    assert "1m 5s" in subtitle.plain
    assert "10:01:05" in subtitle.plain
