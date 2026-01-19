import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MAX_RETRIES
from copium_loop.state import AgentState
from copium_loop.utils import get_lint_command, get_test_command, notify, run_command


async def tester(state: AgentState) -> dict:
    print("--- Test Runner Node ---")
    retry_count = state.get("retry_count", 0)

    try:
        # 1. Run Linter
        lint_cmd, lint_args = get_lint_command()
        print(f"Running {lint_cmd} {' '.join(lint_args)}...")
        lint_result = await run_command(lint_cmd, lint_args)
        lint_output = lint_result["output"]

        if lint_result["exit_code"] != 0:
            print("Linter failed.")
            message = (
                "Max retries exceeded. Aborting."
                if retry_count >= MAX_RETRIES
                else "Linting failed. Returning to coder."
            )
            await notify("Workflow: Linting Failed", message, 4)

            return {
                "test_output": "FAIL (Lint):\n" + lint_output,
                "retry_count": retry_count + 1,
                "messages": [
                    SystemMessage(
                        content=f"Linting failed ({lint_cmd} {' '.join(lint_args)}):\n"
                        + lint_output
                    )
                ],
            }

        # 2. Run Unit Tests
        test_cmd, test_args = get_test_command()

        print(f"Running {test_cmd} {' '.join(test_args)}...")
        result = await run_command(test_cmd, test_args)
        unit_output = result["output"]
        exit_code = result["exit_code"]

        # More robust test failure detection
        # We look for common patterns in pytest, npm test, etc.
        # "FAILURES", "ERRORS", "FAILED", "FAIL", "error:"
        failure_patterns = [
            r"FAILURES",
            r"ERRORS",
            r"\d+ failed",
            r"\d+ error",
            r"FAIL\b",
            r"FAILED\b",
            r"^error:",
        ]

        has_failed = exit_code != 0
        if not has_failed:
            for pattern in failure_patterns:
                if re.search(pattern, unit_output, re.MULTILINE | re.IGNORECASE):
                    has_failed = True
                    break

        if has_failed:
            message = (
                "Max retries exceeded. Aborting."
                if retry_count >= MAX_RETRIES
                else "Unit tests failed. Returning to coder."
            )
            await notify("Workflow: Tests Failed", message, 4)

            return {
                "test_output": "FAIL (Unit):\n" + unit_output,
                "retry_count": retry_count + 1,
                "messages": [
                    SystemMessage(content="Tests failed (Unit):\n" + unit_output)
                ],
            }

        return {"test_output": "PASS"}
    except Exception as error:
        return {
            "test_output": "FAIL: " + str(error),
            "retry_count": retry_count + 1,
        }
