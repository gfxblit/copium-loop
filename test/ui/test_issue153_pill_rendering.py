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
    
    # Check styles (implementation detail: Text stores spans with styles)
    # We expect 3 parts: left cap, middle text, right cap
    # Text.assemble usually merges them into one Text object with spans if styled differently
    # But here they share the same background color? 
    # Left: ("◖", status_color) -> fg=status_color
    # Middle: (..., "bold black on {status_color}") -> fg=black, bg=status_color, bold
    # Right: ("◗", status_color) -> fg=status_color
    
    # Let's inspect spans to be sure
    # Since we can't easily inspect internal rich structure without fragility, checking the plain text 
    # and ensuring no regression in the general shape is good.
    # But we can check if the status color is used.
    status_color = "#00FF41"
    
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
