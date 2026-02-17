## 2024-05-22 - [Textual Widget Verification]
**Learning:** `SessionWidget`s in `TextualDashboard` are completely rebuilt when the visible session list changes (e.g., paging). This means we can safely pass state like `index` (for keyboard shortcuts) in `__init__` without worrying about complex update logic for reused widgets, as long as `update_ui` handles the recreation correctly.
**Action:** When adding per-session UI state that depends on the list position, pass it during widget initialization in `update_ui`.

## 2024-05-22 - [Textual Testing]
**Learning:** Verifying `Textual` widget content in tests is best done by querying the widget via ID and checking its rendered output using `widget.render()`, rather than inspecting internal properties which might not reflect the final TUI representation.
**Action:** Use `app.query_one("#id").render()` to verify visual text content in TUI tests.
