from copium_loop.ui.pillar import MatrixPillar


def test_matrix_pillar_title_rendering_issue153():
    """Verify that MatrixPillar title rendering matches Issue 153 requirements (pill shape)."""
    pillar = MatrixPillar("CODER")

    # 1. Active Status
    # Requirement: ◖ (U+25D6) ... ▶ {name} ... ◗ (U+25D7)
    # Color: Neon Green (#00FF41) for ends, bold black on #00FF41 for text
    pillar.status = "active"
    title = pillar.get_title_text()
    plain = title.plain

    assert "◖" in plain
    assert "◗" in plain
    assert " ▶ CODER " in plain

    # Verify styles are present
    assert len(title.spans) > 0
    # At least one span should contain the status color in its style definition
    status_color = pillar.get_status_color()
    assert any(status_color in str(span.style) for span in title.spans)

    # 2. Success Status
    # Requirement: ◖ ... ✔ {name} ... ◗
    # Color: Cyan
    pillar.status = "success"
    title = pillar.get_title_text()
    plain = title.plain

    assert "◖" in plain
    assert "◗" in plain
    assert " ✔ CODER " in plain

    # 3. Failure Status
    # Requirement: ◖ ... ✘ {name} ... ◗
    # Color: Red (or whatever failure color is defined as)
    pillar.status = "failed"
    title = pillar.get_title_text()
    plain = title.plain

    assert "◖" in plain
    assert "◗" in plain
    assert " ✘ CODER " in plain

    # 4. Idle Status (No pill)
    pillar.status = "idle"
    title = pillar.get_title_text()
    plain = title.plain

    assert "◖" not in plain
    assert "◗" not in plain
    assert "○ CODER" in plain
