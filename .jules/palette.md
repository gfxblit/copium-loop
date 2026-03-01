## 2026-02-18 - Textual Empty States
**Learning:** Textual containers render as blank space when empty, which can be confused for a frozen application.
**Action:** When a main container has no children, always mount a dedicated `Label` or widget with a clear "Empty State" message and call-to-action.
## 2026-03-01 - Textual Keyboard Shortcuts
**Learning:** Keyboard shortcuts 1-9 were bound to tmux switch actions, but there were no visual hints on the `SessionWidget` headers making them undiscoverable.
**Action:** Add optional `index` parameter to list widgets and prepend `[index] ` to their display names to provide keyboard shortcut hints.
