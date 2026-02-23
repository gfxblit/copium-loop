import asyncio
import json
import time
from datetime import datetime

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from textual.css.scalar import Unit

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.pillar import MatrixPillar
from copium_loop.ui.renderable import TailRenderable
from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


def test_matrix_pillar_render_order():
    """Test that MatrixPillar renders logs in chronological order (oldest to newest)."""
    pillar = MatrixPillar("Coder")
    pillar.add_line("first")
    pillar.add_line("second")
    pillar.add_line("third")

    panel = pillar.render()
    assert isinstance(panel, Panel)

    # We need to verify the content of the panel
    console = Console(width=20)
    with console.capture() as capture:
        console.print(panel)

    output = capture.get()
    # Chronological order: first, second, third (top to bottom)
    first_idx = output.find("first")
    second_idx = output.find("second")
    third_idx = output.find("third")

    assert first_idx != -1
    assert second_idx != -1
    assert third_idx != -1
    assert first_idx < second_idx < third_idx


def test_matrix_pillar_status_and_duration():
    """Test that MatrixPillar correctly tracks status and duration."""
    pillar = MatrixPillar("Coder")

    # Initial state
    assert pillar.status == "idle"
    assert pillar.duration is None

    # Set to active
    timestamp = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp)
    assert pillar.status == "active"

    # Set to success after 10 seconds
    timestamp_end = "2026-01-25T12:00:10"
    pillar.set_status("success", timestamp_end)
    assert pillar.status == "success"
    assert pillar.duration == 10.0
    assert pillar.completion_time is not None


def test_matrix_pillar_buffer_limit():
    """Test that MatrixPillar respects its max_buffer size."""
    pillar = MatrixPillar("Coder")
    pillar.max_buffer = 5

    for i in range(10):
        pillar.add_line(f"line {i}")

    assert len(pillar.buffer) == 5
    assert pillar.buffer[0]["line"] == "line 5"
    assert pillar.buffer[-1]["line"] == "line 9"


def test_matrix_pillar_filtering():
    """Test that MatrixPillar can filter lines by source."""
    pillar = MatrixPillar("coder")

    pillar.add_line("LLM output 1", source="llm")
    pillar.add_line("System info 1", source="system")
    pillar.add_line("LLM output 2", source="llm")

    renderable_llm = pillar.get_content_renderable(show_system=False)
    assert len(renderable_llm.buffer) == 2
    assert "LLM output 1" in renderable_llm.buffer[0]
    assert "LLM output 2" in renderable_llm.buffer[1]

    renderable_all = pillar.get_content_renderable(show_system=True)
    assert len(renderable_all.buffer) == 3

    # Test that headers (--- ... ---) are always visible
    pillar.add_line("--- CODER Node ---", source="system")
    renderable_header = pillar.get_content_renderable(show_system=False)
    # LLM output 1, LLM output 2, and the header
    assert any("--- CODER Node ---" in line for line in renderable_header.buffer)

    # Lean node should return an empty TailRenderable
    pillar_lean = MatrixPillar("tester")
    pillar_lean.add_line("tester log")
    renderable_lean = pillar_lean.get_content_renderable()
    assert isinstance(renderable_lean, TailRenderable)
    assert len(renderable_lean.buffer) == 0


def test_matrix_pillar_time_suffix():
    """Test time suffix rendering in MatrixPillar."""
    pillar = MatrixPillar("Coder")

    # Active
    pillar.start_time = time.time() - 65  # 1m 5s
    pillar.status = "active"
    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "1m 5s" in output

    # Success with completion time
    pillar.status = "success"
    pillar.completion_time = time.time()
    pillar.duration = 65
    panel = pillar.render()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "1m 5s" in output
    assert "@" in output  # Time of completion


def test_pillar_status_constants_are_frozensets():
    """Verify that status constants are frozensets as requested in PR review."""
    assert isinstance(MatrixPillar.COMPLETION_STATUSES, frozenset)
    assert isinstance(MatrixPillar.SUCCESS_STATUSES, frozenset)
    assert isinstance(MatrixPillar.FAILURE_STATUSES, frozenset)


def test_matrix_pillar_journaler_completion_status():
    """Test that journaler statuses (journaled, no_lesson) correctly trigger completion metrics."""
    pillar = MatrixPillar("Journaler")

    # Start active
    timestamp_start = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp_start)
    assert pillar.status == "active"
    assert pillar.start_time is not None

    # Set to 'journaled' after 10 seconds
    timestamp_end = "2026-01-25T12:00:10"
    pillar.set_status("journaled", timestamp_end)

    assert pillar.status == "journaled"
    assert pillar.duration == 10.0
    assert pillar.completion_time is not None

    # Render check
    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    # Should contain duration and completion timestamp
    assert "10s" in output
    assert "@" in output


def test_matrix_pillar_journaler_no_lesson_completion_status():
    """Test that 'no_lesson' status also triggers completion metrics."""
    pillar = MatrixPillar("Journaler")

    timestamp_start = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp_start)

    timestamp_end = "2026-01-25T12:00:05"
    pillar.set_status("no_lesson", timestamp_end)

    assert pillar.status == "no_lesson"
    assert pillar.duration == 5.0
    assert pillar.completion_time is not None

    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    assert "5s" in output
    assert "@" in output


def test_matrix_pillar_title_and_subtitle():
    pillar = MatrixPillar("coder")

    # Test idle state
    title = pillar.get_title_text()
    subtitle = pillar.get_subtitle_text()
    assert isinstance(title, Text)
    assert title.plain == " ○ CODER "
    assert subtitle.plain == ""

    # Test active state
    pillar.set_status("active", datetime.now().isoformat())
    title = pillar.get_title_text()
    assert title.plain == " ▶ CODER "

    # Test success state
    pillar.set_status("success", datetime.now().isoformat())
    title = pillar.get_title_text()
    subtitle = pillar.get_subtitle_text()
    assert title.plain == " ✔ CODER "
    assert "SUCCESS" in subtitle.plain
    assert "@" in subtitle.plain


def test_matrix_pillar_duration_in_subtitle():
    pillar = MatrixPillar("coder")
    start_time = datetime(2026, 2, 16, 10, 0, 0)
    end_time = datetime(2026, 2, 16, 10, 1, 5)  # 1m 5s duration

    pillar.set_status("active", start_time.isoformat())
    pillar.set_status("success", end_time.isoformat())

    subtitle = pillar.get_subtitle_text()
    assert "1m 5s" in subtitle.plain
    assert "10:01:05" in subtitle.plain


def test_actual_node_names_in_ui():
    """Verify that actual node names are used as headers in the UI."""
    session = SessionColumn("test_session")

    expected_nodes = [
        "coder",
        "tester",
        "architect",
        "reviewer",
        "pr_pre_checker",
        "pr_creator",
    ]

    layout = session.render(column_width=80)
    console = Console(width=80)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get().upper()

    for node in expected_nodes:
        assert node.upper() in output

    assert "JOURNALER" not in output
    assert "JOURNAL" not in output


@pytest.mark.asyncio
async def test_dynamic_node_discovery_in_ui(tmp_path):
    """Verify that new nodes appearing in logs are dynamically added to the UI."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test_session.jsonl"

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    async with app.run_test() as pilot:
        event = {
            "node": "security_scanner",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-03T12:00:00",
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        await app.update_from_logs()
        await pilot.pause()

        widget = app.query_one("#session-test_session")
        assert widget is not None
        assert "security_scanner" in widget.session_column.pillars

        journaler_event = {
            "node": "journaler",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-03T12:05:00",
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(journaler_event) + "\n")

        await app.update_from_logs()
        await pilot.pause()

        assert "journaler" in widget.session_column.pillars

        for _ in range(10):
            try:
                app.query_one("#pillar-test_session-security_scanner")
                break
            except Exception:
                await asyncio.sleep(0.1)

        pillar_widget = app.query_one("#pillar-test_session-security_scanner")
        assert pillar_widget is not None


def test_matrix_pillar_architect_statuses():
    """Test that architect statuses correctly trigger completion metrics."""
    pillar_ok = MatrixPillar("Architect")
    timestamp_start = "2026-02-03T10:00:00"
    pillar_ok.set_status("active", timestamp_start)

    timestamp_end_ok = "2026-02-03T10:00:10"
    pillar_ok.set_status("ok", timestamp_end_ok)

    assert pillar_ok.status == "ok"
    assert pillar_ok.duration == 10.0
    assert pillar_ok.completion_time is not None

    panel_ok = pillar_ok.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel_ok)
    output_ok = capture.get()

    assert "✔" in output_ok
    assert "10s" in output_ok
    assert "@" in output_ok

    pillar_refactor = MatrixPillar("Architect")
    pillar_refactor.set_status("active", timestamp_start)

    timestamp_end_refactor = "2026-02-03T10:00:15"
    pillar_refactor.set_status("refactor", timestamp_end_refactor)

    assert pillar_refactor.status == "refactor"
    assert pillar_refactor.duration == 15.0
    assert pillar_refactor.completion_time is not None

    panel_refactor = pillar_refactor.render()
    with console.capture() as capture:
        console.print(panel_refactor)
    output_refactor = capture.get()

    assert "✘" in output_refactor
    assert "15s" in output_refactor
    assert "@" in output_refactor


def test_pillar_set_status_invalid_timestamp():
    p = MatrixPillar("Coder")
    p.set_status("active", "invalid-timestamp")
    assert p.status == "active"
    assert p.start_time is None


def test_pillar_render_duration_seconds():
    p = MatrixPillar("Coder")
    p.start_time = time.time() - 30
    p.status = "active"
    panel = p.render()
    assert "s]" in str(panel.subtitle)


def test_pillar_render_duration_minutes_exact():
    p = MatrixPillar("Coder")
    p.start_time = time.time() - 120
    p.status = "active"
    panel = p.render()
    assert "[2m]" in str(panel.subtitle)


def test_pillar_render_error_status():
    p = MatrixPillar("Coder")
    p.status = "error"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"


def test_pillar_render_rejected_status():
    p = MatrixPillar("Reviewer")
    p.status = "rejected"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"


def test_pillar_render_failed_status():
    p = MatrixPillar("Tester")
    p.status = "failed"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"


def test_pillar_render_pr_failed_status():
    p = MatrixPillar("PR Creator")
    p.status = "pr_failed"
    panel = p.render()
    assert "✘" in str(panel.title)
    assert panel.border_style == "red"


def test_pillar_render_idle_empty():
    p = MatrixPillar("Coder")
    p.status = "idle"
    panel = p.render()
    assert "○" in str(panel.title)
    assert panel.border_style == "#666666"


@pytest.mark.asyncio
async def test_pillar_weighting_many_nodes(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test-session.jsonl"

    events = []
    for i in range(10):
        events.append(
            {
                "node": f"node-{i}",
                "event_type": "status",
                "data": "idle",
                "timestamp": f"2026-02-09T12:00:{i:02d}",
            }
        )

    events.append(
        {
            "node": "node-5",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-09T12:01:00",
        }
    )

    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        app.query_one(SessionWidget)
        pillars = app.query(PillarWidget)
        assert len(pillars) >= 10

        node_5_pillar = app.query_one("#pillar-test-session-node-5", PillarWidget)
        node_0_pillar = app.query_one("#pillar-test-session-node-0", PillarWidget)

        assert node_5_pillar.styles.height.value == 100.0
        assert node_0_pillar.styles.height.value == 1.0


@pytest.mark.asyncio
async def test_pillar_weighting_active_node(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test-session.jsonl"

    events = [
        {
            "node": "coder",
            "event_type": "status",
            "data": "idle",
            "timestamp": "2026-02-09T12:00:00",
        },
        {
            "node": "architect",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-09T12:00:01",
        },
    ]
    log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        coder_pillar = app.query_one("#pillar-test-session-coder", PillarWidget)
        architect_pillar = app.query_one("#pillar-test-session-architect", PillarWidget)

        assert coder_pillar.styles.height.unit == Unit.FRACTION
        assert architect_pillar.styles.height.unit == Unit.FRACTION

        assert architect_pillar.styles.height.value == 100.0
        assert coder_pillar.styles.height.value == 1.0


class TestPillarStatusNames:
    def test_pillar_shows_specific_failure_status_names(self):
        # Architect REFACTOR
        pillar = MatrixPillar("Architect")
        pillar.status = "refactor"
        subtitle = pillar.get_subtitle_text()
        assert "REFACTOR" in subtitle.plain
        assert "FAILED" not in subtitle.plain

        # Reviewer REJECTED
        pillar = MatrixPillar("Reviewer")
        pillar.status = "rejected"
        subtitle = pillar.get_subtitle_text()
        assert "REJECTED" in subtitle.plain
        assert "FAILED" not in subtitle.plain

        # Tester FAILED
        pillar = MatrixPillar("Tester")
        pillar.status = "failed"
        subtitle = pillar.get_subtitle_text()
        assert "FAILED" in subtitle.plain

        # Error
        pillar = MatrixPillar("Coder")
        pillar.status = "error"
        subtitle = pillar.get_subtitle_text()
        assert "ERROR" in subtitle.plain
