# Implementation Plan - Url references to Jules sessions

## Overview
Currently, the Jules engine logs internal session identifiers (e.g., `sessions/127869...`). To improve the debugging experience, these should be replaced with clickable URLs (e.g., `https://jules.google.com/session/127869...`) in stdout, telemetry logs, and error messages.

## Requirements
-   **Log URLs:** When a Jules session is created or resumed, log the full URL to the session, not just the internal name.
-   **Error Messages:** Exception messages involving session failures should include the session URL.
-   **Telemetry:** Ensure these URL-containing messages are logged to telemetry so they appear in the dashboard and are picked up by state reconstruction logic.

## Architecture Changes

### `src/copium_loop/engine/jules.py`
-   Add a private helper method `_get_session_url(self, session_name: str) -> str` to `JulesEngine`.
    -   It should parse the numeric ID from `sessions/<id>` and return `https://jules.google.com/session/<id>`.
-   Update `invoke` method:
    -   Replace `print(f"[{node}] Found existing Jules session: {session_name}")` with the URL version.
    -   Replace `print(f"Jules session created: {session_name}")` with the URL version.
    -   **Crucial:** Ensure these messages are explicitly logged to telemetry using `get_telemetry().log_output(node, msg)` so they are visible in the UI and persisted for state reconstruction.
-   Update `_poll_session` method:
    -   Update `JulesSessionError` messages to use the URL.

### `src/copium_loop/telemetry.py`
-   No code changes required, but verify that `reconstruct_state` still correctly identifies the engine type based on the string "Jules session created".

## Implementation Steps

### Phase 1: Engine Updates
1.  **Modify `src/copium_loop/engine/jules.py`**:
    -   Implement `_get_session_url`.
    -   Update the logging logic in `invoke` to use this helper and `telemetry.log_output`.
    -   Update error raising in `invoke` and `_poll_session`.

### Phase 2: Test Updates
1.  **Update `test/engine/test_jules_api.py`**:
    -   Modify `test_jules_api_invoke_success` (and others) to expect the URL in the output.
    -   Update `test_jules_api_failure_state` to match the URL in the exception message.
    -   Update `test_jules_api_creation_error` if applicable.
2.  **Update `test/test_telemetry.py`**:
    -   Update `test_reconstruct_jules_engine` to use the new log format string `Jules session created: https://...`.

## Testing Strategy
-   Run `pytest test/engine/test_jules_api.py` to verify API interactions and error messages.
-   Run `pytest test/test_telemetry.py` to verify state reconstruction.
-   Run `pytest` to ensure no regressions.
