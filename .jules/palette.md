## 2026-02-18 - Textual Empty States
**Learning:** Textual containers render as blank space when empty, which can be confused for a frozen application.
**Action:** When a main container has no children, always mount a dedicated `Label` or widget with a clear "Empty State" message and call-to-action.

## 2026-03-05 - Implicit Key Bindings
**Learning:** Key bindings that map to list indices (like 1-9 for sessions) are invisible without explicit visual cues in the list items themselves.
**Action:** When implementing numeric shortcuts for list items, always display the corresponding number (e.g., `[1]`) prominently in the item's header or label.
