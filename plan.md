# Implementation Plan: Fix Verbose Journaler (Issue #46)

## Overview
The Journaler node is currently recording "change logs" (descriptions of what was just done) as project memories, rather than extracting actionable principles for future use. This plan updates the Journaler's prompt to strictly enforce that memories must be future-facing principles or constraints, explicitly rejecting past-tense summaries of actions.

## Requirements
- **No Change Logs:** The Journaler must NOT output summaries of actions taken (e.g., "Fixed bug in X", "Added feature Y").
- **Principles Only:** Memories must be phrased as actionable advice or constraints for future agents (e.g., "Always use X for Y", "Avoid Z because it causes W").
- **Clear Examples:** The prompt must include explicit examples of "BAD" (log-style) vs "GOOD" (principle-style) memories to guide the LLM.

## Architecture Changes
- **File:** `src/copium_loop/nodes/journaler.py`
  - Modify the `prompt` string within the `journaler` function.

## Implementation Steps

### Phase 1: Prompt Refinement
1. **Update Journaler Prompt** (File: `src/copium_loop/nodes/journaler.py`)
   - Action: Rewrite the "DECISION LOGIC" and "RULES" sections of the system prompt.
   - Details:
     - Add a "ANTI-PATTERNS" or "WHAT NOT TO LOG" section.
     - Add a "PRINCIPLES" section.
     - Provide concrete examples:
       - **Bad:** "The journaler node now deduplicates learnings."
       - **Good:** "Deduplicate learnings by checking against existing memories before logging."
   - Why: To stop the accumulation of low-value, noisy memories.
   - Dependencies: None.
   - Risk: Low.

### Phase 2: Verification
2. **Update Tests** (File: `test/nodes/test_journaler.py`)
   - Action: Add a test case `test_journaler_prompt_bans_changelogs` to verify the prompt contains the new instructions.
   - Why: To prevent regression if the prompt is simplified later.
   - Dependencies: Phase 1.

## Testing Strategy
- **Unit Tests:** Run `pytest test/nodes/test_journaler.py` to ensure the prompt is correctly constructed and the journaler flow remains intact.
- **Manual Verification:** (Optional/Post-Merge) Observe the next run's journal output to see if it produces a principle instead of a log.

## Risks & Mitigations
- **Risk:** The LLM might still output logs if the diff is too overwhelming.
  - **Mitigation:** The prompt explicitly instructs to output "NO_LESSON" if no clear principle exists, which is safer than a bad memory.
