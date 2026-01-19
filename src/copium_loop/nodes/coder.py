from langchain_core.messages import SystemMessage

from copium_loop.constants import DEFAULT_MODELS
from copium_loop.state import AgentState
from copium_loop.utils import invoke_gemini


async def coder(state: AgentState) -> dict:
    print("--- Coder Node ---")
    messages = state["messages"]
    test_output = state.get("test_output", "")
    review_status = state.get("review_status", "")

    initial_request = messages[0].content

    system_prompt = f"""You are a software engineer. Implement the following request: {initial_request}.
    You have access to the file system and git.

    IMPORTANT: You MUST commit your changes using git. You may create multiple commits if it makes sense for the task.
    Please output the code changes in markdown blocks as well for the conversation record."""

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
    )
    print("\nCoding complete.")

    return {
        "code_status": "coded",
        "messages": [SystemMessage(content=code_content)],
    }
