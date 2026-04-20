## 2026-02-18 - Textual Empty States
**Learning:** Textual containers render as blank space when empty, which can be confused for a frozen application.
**Action:** When a main container has no children, always mount a dedicated `Label` or widget with a clear "Empty State" message and call-to-action.

## 2026-02-19 - Keyboard Shortcut Discoverability
**Learning:** TUI users often rely on keyboard shortcuts (like `1`-`9`) to navigate lists, but these are invisible without explicit indicators.
**Action:** When iterating through a list of items that have associated shortcuts, display the shortcut key (e.g., `[1]`) prominently in the item's header.
