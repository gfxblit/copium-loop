import re

from langchain_core.messages import SystemMessage

from copium_loop import constants
from copium_loop.discovery import get_build_command, get_lint_command, get_test_command
from copium_loop.languages import Command, CompositeCommand
from copium_loop.nodes.utils import node_header
from copium_loop.shell import run_command
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


async def _run_stage(
    stage_name: str, cmd_obj: Command | CompositeCommand, telemetry
) -> tuple[bool, str]:
    """Runs a single stage (lint, build, or test) and logs telemetry."""
    if not cmd_obj:
        return True, ""

    msg = f"Running {stage_name}...\n"
    telemetry.log_info("tester", msg)
    print(msg, end="")

    commands = cmd_obj.commands if isinstance(cmd_obj, CompositeCommand) else [cmd_obj]

    all_outputs = []
    overall_success = True
    final_exit_code = 0

    for cmd in commands:
        result = await run_command(cmd.executable, cmd.args, node="tester", cwd=cmd.cwd)
        output = result["output"]
        exit_code = result["exit_code"]
        all_outputs.append(output)

        if exit_code != 0:
            overall_success = False
            final_exit_code = exit_code
            break

    combined_output = "\n".join(all_outputs)
    success = overall_success and final_exit_code == 0

    # Special failure detection for linting and unit tests
    if (stage_name == "linting" or stage_name == "unit tests") and success:
        failure_patterns = [
            r"\b[1-9]\d* (failed|failing)\b",
            r"\b[1-9]\d* errors?\b",
            r"Found \d+ errors?",
            r"^={3,}\s+ERRORS\s+={3,}$",
            r"^={3,}\s+FAILURES\s+={3,}$",
            r"^\s*FAIL\b",
            r"^\s*FAILED\b",
            r"^\s*error:",
            r"(?<![/\\])\berror:",
            r"\bUnreachable code\b",
        ]

        # Linter specific codes (e.g. E401, F401, PLR0915)
        # We only check these for the linting stage to avoid false positives in unit tests.
        if stage_name == "linting":
            failure_patterns.append(r":\d+:(\d+:)?\s*[A-Z]+\d{3,4}\b")

        for pattern in failure_patterns:
            if re.search(pattern, combined_output, re.IGNORECASE | re.MULTILINE):
                success = False
                break

    if not success:
        telemetry.log_info("tester", f"{stage_name.capitalize()} failed.\n")
        print(f"{stage_name.capitalize()} failed.")

    return success, combined_output


@node_header("tester", status_key="test_output")
async def tester_node(state: AgentState) -> dict:
    telemetry = get_telemetry()

    retry_count = state.get("retry_count", 0)

    # 1. Lint
    lint_cmd_obj = get_lint_command()
    if lint_cmd_obj:
        success, output = await _run_stage("linting", lint_cmd_obj, telemetry)
        if not success:
            telemetry.log_status("tester", "failed")
            error_msg = "FAIL (Lint):\n" + output
            return {
                "test_output": error_msg,
                "retry_count": retry_count + 1,
                "messages": [
                    SystemMessage(
                        content=f"Linting failed ({lint_cmd_obj}):\n" + output
                    )
                ],
                "last_error": error_msg,
            }

    # 2. Build
    build_cmd_obj = get_build_command()
    if build_cmd_obj:
        success, output = await _run_stage("build", build_cmd_obj, telemetry)
        if not success:
            telemetry.log_status("tester", "failed")
            error_msg = "FAIL (Build):\n" + output
            return {
                "test_output": error_msg,
                "retry_count": retry_count + 1,
                "messages": [
                    SystemMessage(content=f"Build failed ({build_cmd_obj}):\n" + output)
                ],
                "last_error": error_msg,
            }

    # 3. Test
    test_cmd_obj = get_test_command()
    if test_cmd_obj:
        success, output = await _run_stage("unit tests", test_cmd_obj, telemetry)
        if not success:
            telemetry.log_status("tester", "failed")
            message = (
                "Max retries exceeded. Aborting."
                if retry_count >= constants.MAX_RETRIES
                else "Unit tests failed. Returning to coder."
            )

            # Check for coverage failures
            coverage_patterns = [
                r"Required test coverage of \d+% not reached\. Total coverage: ([\d.]+)%",
                r"Jest: Coverage for .+? \(([\d.]+)%\) does not meet global threshold \(([\d.]+)%\)",
                r"Coverage check failed",
            ]
            is_coverage_failure = any(
                re.search(p, output, re.MULTILINE) for p in coverage_patterns
            )

            fail_type = "Coverage" if is_coverage_failure else "Unit"
            fail_prefix = f"FAIL ({fail_type}):"

            if is_coverage_failure:
                message = (
                    "Max retries exceeded. Aborting."
                    if retry_count >= constants.MAX_RETRIES
                    else "Test coverage threshold not met. Returning to coder."
                )

            telemetry.log_info("tester", f"{message}\n")
            error_msg = f"{fail_prefix}\n" + output
            return {
                "test_output": error_msg,
                "retry_count": retry_count + 1,
                "messages": [
                    SystemMessage(content=f"Tests failed ({fail_type}):\n" + output)
                ],
                "last_error": error_msg,
            }

    telemetry.log_status("tester", "success")
    return {"test_output": "PASS"}
