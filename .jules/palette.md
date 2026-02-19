## 2026-02-18 - Textual Empty States
**Learning:** Textual containers render as blank space when empty, which can be confused for a frozen application.
**Action:** When a main container has no children, always mount a dedicated `Label` or widget with a clear "Empty State" message and call-to-action.
