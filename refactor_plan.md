# Refactor Plan: Engine State Side-Channel (Issue #159)

The current implementation of `jules_metadata` in `AgentState` couples nodes and the engine interface to infrastructure concerns (session IDs). This plan moves engine-specific state into a persistent side-channel managed by `SessionManager`.

## 1. Generalize `SessionManager`
**File**: `src/copium_loop/session_manager.py`
- Modify `SessionData` to replace `jules_sessions` with a generic `engine_state: dict[str, dict[str, Any]]`.
- Add `get_engine_state(engine_type, key)` and `update_engine_state(engine_type, key, value)` methods.
- Provide backward compatibility for existing `jules_sessions` data during migration if possible, or just pivot to the new structure.

## 2. Update `LLMEngine` Base Class
**File**: `src/copium_loop/engine/base.py`
- Remove `jules_metadata` from the `invoke` method signature.
- Replace it with `**kwargs: Any` for future-proofing.
- Add an optional `set_session_manager(session_manager: SessionManager)` method (or include it in `__init__` if practical, but `WorkflowManager` creates engines via factory, so a setter is safer).

## 3. Internalize Session Logic in `JulesEngine`
**File**: `src/copium_loop/engine/jules.py`
- Update `invoke` to remove the `jules_metadata` parameter.
- Use the internal `SessionManager` (if bound) to retrieve/persist session IDs using the `node` name as the lookup key.
- This keeps session resumption logic entirely hidden from the caller.

## 4. Purge `jules_metadata` from Workflow
**Files**: 
- `src/copium_loop/state.py`: Remove `jules_metadata` from `AgentState`.
- `src/copium_loop/copium_loop.py`: 
    - Remove metadata injection in `run()`.
    - Remove metadata extraction/persistence in `_wrap_node()`.
    - Inject `SessionManager` into the `engine` instance after creation.
- `src/copium_loop/nodes/*.py`: 
    - Remove all reading and returning of `jules_metadata`.
    - Nodes should only pass `node="name"` to `engine.invoke()`.

## 5. Verification
- Update tests in `test/engine/` and `test/test_issue159_state_refactor.py` to reflect the cleaner interface.
- Ensure `SessionManager` correctly persists engine state to disk.
- Verify that Jules session resumption still works by running a multi-node workflow.
