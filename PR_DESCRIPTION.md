Implemented Architect Convergence Fix (Issue #183) with improved SOLID architecture:
1.  **Centralized Git Logic**: Consolidated HEAD hash retrieval into `copium_loop.git.get_head` with robust error handling and fallback to "unknown".
2.  **State-Driven Cache Busting**: Added `head_hash` to `AgentState` to ensure prompt cache-busting is consistent and performant.
3.  **Automatic Hash Refresh**: Implemented automatic `head_hash` refresh in `WorkflowManager` wrapper before each node execution to maintain accuracy throughout the session.
4.  **Prompt Integration**:
    - Updated `get_architect_prompt`, `get_reviewer_prompt`, `get_coder_prompt`, and `journaler_node` to use the injected `head_hash`.
    - Prompts now explicitly include `(Current HEAD: <hash>)` to force unique sessions in engines like Jules.
5.  **Quality & Verification**:
    - Comprehensive test coverage in `test/nodes/test_issue183_convergence.py`.
    - Updated `test/nodes/test_utils.py` to align with the new state-based architecture.
    - All 122 node tests pass.
    - Adheres to SOLID (DIP/SRP) principles and optimized for performance.
