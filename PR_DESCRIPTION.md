Implemented Architect Convergence Fix (Issue #183):
1.  **Cache Busting**: Implemented `get_head_hash` in `copium_loop.nodes.utils` to retrieve the current git HEAD hash.
2.  **Prompt Updates**: 
    - Updated `get_architect_prompt` (Jules) to include `(Current HEAD: <hash>)`.
    - Updated `get_reviewer_prompt` (Jules) to include `(Current HEAD: <hash>)`.
    - Updated `get_coder_prompt` (All engines) to include `(Current HEAD: <hash>)`.
    - Updated `journaler_node` to include `(Current HEAD: <hash>)`.
3.  **Verification**: Added `test/nodes/test_issue183_convergence.py` covering all modified prompts.
4.  **Quality**: All tests pass, and code adheres to linting standards.