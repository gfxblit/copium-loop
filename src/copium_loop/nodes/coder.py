from langchain_core.messages import SystemMessage

from copium_loop.constants import DEFAULT_MODELS
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry
from copium_loop.utils import invoke_gemini


async def coder(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("coder", "active")
    print("--- Coder Node ---")
    messages = state["messages"]
    test_output = state.get("test_output", "")
    review_status = state.get("review_status", "")

    initial_request = messages[0].content

    system_prompt = f"""You are a software engineer. Implement the following request: {initial_request}.
    You have access to the file system and git.

    CRITICAL: You MUST follow Test-Driven Development (TDD) methodology.
    To do this, you MUST activate the 'tdd-guide' skill and follow its Red-Green-Refactor cycle:
    1. Write tests FIRST (they should fail initially)
    2. Run tests to verify they fail
    3. Write minimal implementation to make tests pass
    4. Run tests to verify they pass
    5. Refactor and ensure 80%+ test coverage
    6. Run linting to ensure code quality

    After the skill completes its guidance, implement the code following TDD principles.
    Do not skip writing tests - they are mandatory for all new functionality.
    Always run the test suite and the linter to verify your changes.
    The test suite will now report coverage - ensure it remains high (80%+).

    IMPORTANT: You MUST commit your changes using git. You may create multiple commits if it makes sense for the task.
    When resolving conflicts or rebasing, ALWAYS use the '--no-edit' flag (e.g., 'git rebase --continue --no-edit' or 'git commit --no-edit') to avoid interactive editors."""

    if test_output and ("FAIL" in test_output or "failed" in test_output):
        system_prompt = f"""Your previous implementation failed tests.

    TEST OUTPUT:
    {test_output}

    Please fix the code to satisfy the tests and the original request: {initial_request}."""
        system_prompt += "\n\nMake sure to commit your fixes."
    elif review_status == "rejected":
        last_message = messages[-1]
        system_prompt = f"""Your previous implementation was rejected by the reviewer.

    REVIEWER FEEDBACK:
    {last_message.content}

    Please fix the code to satisfy the reviewer and the original request: {initial_request}."""
        system_prompt += "\n\nMake sure to commit your fixes."
    elif review_status == "pr_failed":
        last_message = messages[-1]
        system_prompt = f"""Your previous attempt to create a PR failed.

    ERROR:
    {last_message.content}

    Please fix any issues (e.g., git push failures, branch issues) and try again.
    Original request: {initial_request}"""
        system_prompt += "\n\nMake sure to commit your fixes if necessary."
    if review_status == "needs_commit":
        system_prompt = f"""You have uncommitted changes that prevent PR creation.
    Please review your changes and commit them using git.
    Original request: {initial_request}"""

    # Start with "auto" (None), then fallback to default models
    coder_models = [None] + DEFAULT_MODELS
    code_content = await invoke_gemini(
        system_prompt,
        ["--yolo"],
        models=coder_models,
        verbose=state.get("verbose"),
        label="Coder System",
        node="coder",
    )
    print("\nCoding complete.")
    telemetry.log_status("coder", "idle")

    return {
        "code_status": "coded",
        "messages": [SystemMessage(content=code_content)],
    }
