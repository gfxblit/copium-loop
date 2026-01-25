import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MAX_RETRIES
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry
from copium_loop.utils import (
    get_build_command,
    get_lint_command,
    get_test_command,
    notify,
    run_command,
)


async def tester(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("tester", "active")
    telemetry.log_output("tester", "--- Test Runner Node ---\n")
    print("--- Test Runner Node ---")
    retry_count = state.get("retry_count", 0)

    try:
        # 1. Run Linter
        lint_cmd, lint_args = get_lint_command()
        msg = f"Running {lint_cmd} {' '.join(lint_args)}...\n"
        telemetry.log_output("tester", msg)
        print(msg, end="")
        lint_result = await run_command(lint_cmd, lint_args, node="tester")
        lint_output = lint_result["output"]

        if lint_result["exit_code"] != 0:
            telemetry.log_output("tester", "Linter failed.\n")
            print("Linter failed.")
            telemetry.log_status("tester", "failed")

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

        # 2. Run Build
        build_cmd, build_args = get_build_command()
        if build_cmd:
            msg = f"Running {build_cmd} {' '.join(build_args)}...\n"
            telemetry.log_output("tester", msg)
            print(msg, end="")
            build_result = await run_command(build_cmd, build_args, node="tester")
            build_output = build_result["output"]

            if build_result["exit_code"] != 0:
                telemetry.log_output("tester", "Build failed.\n")
                print("Build failed.")
                telemetry.log_status("tester", "failed")
                return {
                    "test_output": "FAIL (Build):\n" + build_output,
                    "retry_count": retry_count + 1,
                    "messages": [
                        SystemMessage(
                            content=f"Build failed ({build_cmd} {' '.join(build_args)}):\n"
                            + build_output
                        )
                    ],
                }

        # 3. Run Unit Tests
        test_cmd, test_args = get_test_command()

        msg = f"Running {test_cmd} {' '.join(test_args)}...\n"
        telemetry.log_output("tester", msg)
        print(msg, end="")
        result = await run_command(test_cmd, test_args, node="tester")
        unit_output = result["output"]
        exit_code = result["exit_code"]

        # More robust test failure detection
        # We look for common patterns in pytest, npm test, etc.
        # We are conservative if exit_code is 0 to avoid false positives.
        failure_patterns = [
            r"\b[1-9]\d* failed\b",
            r"\b[1-9]\d* errors?\b",
            r"\bFAILURES\b",
            r"\bERRORS\b",
            r"^\s*FAIL\b",
            r"^\s*FAILED\b",
            r"^\s*error:",
        ]

        has_failed = exit_code != 0
        if not has_failed:
            for pattern in failure_patterns:
                if re.search(pattern, unit_output, re.MULTILINE):
                    has_failed = True
                    break

        if has_failed:
            message = (
                "Max retries exceeded. Aborting."
                if retry_count >= MAX_RETRIES
                else "Unit tests failed. Returning to coder."
            )
            telemetry.log_output("tester", f"{message}\n")
            await notify("Workflow: Tests Failed", message, 4)
            telemetry.log_status("tester", "failed")

            return {
                "test_output": "FAIL (Unit):\n" + unit_output,
                "retry_count": retry_count + 1,
                "messages": [
                    SystemMessage(content="Tests failed (Unit):\n" + unit_output)
                ],
            }

        telemetry.log_status("tester", "success")
        return {"test_output": "PASS"}
    except Exception as error:
        telemetry.log_status("tester", "failed")
        return {
            "test_output": "FAIL: " + str(error),
            "retry_count": retry_count + 1,
        }
