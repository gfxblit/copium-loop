## 2026-02-18 - Textual Empty States
**Learning:** Textual containers render as blank space when empty, which can be confused for a frozen application.
**Action:** When a main container has no children, always mount a dedicated `Label` or widget with a clear "Empty State" message and call-to-action.

## 2026-10-24 - Textual Static Widget Testing
**Learning:** `Static` widgets do not expose a `.renderable` attribute as a simple string during tests.
**Action:** To verify the text content of a `Static` widget in tests, inspect `str(widget.render())` instead of `.renderable`.
