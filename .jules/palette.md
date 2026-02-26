## 2026-02-18 - Textual Empty States
**Learning:** Textual containers render as blank space when empty, which can be confused for a frozen application.
**Action:** When a main container has no children, always mount a dedicated `Label` or widget with a clear "Empty State" message and call-to-action.

## 2026-03-01 - TUI Keyboard Shortcuts
**Learning:** In TUI dashboards with dense information, keyboard shortcuts (like 1-9) are only discoverable if the UI explicitly labels the target elements with the corresponding number.
**Action:** Always prepend the shortcut index (e.g., `[1]`) to the header of list items that can be selected via number keys.
