"Core workflow implementation."

import asyncio
import os
import re
import traceback

from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.constants import NODE_TIMEOUT
from copium_loop.discovery import get_test_command
from copium_loop.git import get_head
from copium_loop.graph import create_graph
from copium_loop.notifications import notify
from copium_loop.shell import run_command
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


class WorkflowManager:
    """
    Manages the TDD development workflow using LangGraph and Gemini.
    Orchestrates the coding, testing, and review phases.
    """

    def __init__(self, start_node: str | None = None, verbose: bool = False):
        self.graph = None
        self.start_node = start_node
        self.verbose = verbose

    async def notify(self, title: str, message: str, priority: int = 3):
        """Sends a notification to ntfy.sh if NTFY_CHANNEL is set."""
        await notify(title, message, priority)

    def create_graph(self):
        """Creates and compiles the workflow graph."""
        valid_nodes = ["coder", "tester", "reviewer", "pr_creator"]
        if self.start_node and self.start_node not in valid_nodes:
            print(f'Warning: Invalid start node "{self.start_node}".')
            print(f"Valid nodes are: {', '.join(valid_nodes)}")
            print('Falling back to "coder".')
        self.graph = create_graph(self._wrap_node, self.start_node)
        return self.graph

    def _wrap_node(self, node_name: str, node_func):
        """Wraps a node function with a timeout and error handling."""

        async def wrapper(state: AgentState):
            telemetry = get_telemetry()
            try:
                return await asyncio.wait_for(node_func(state), timeout=NODE_TIMEOUT)
            except asyncio.TimeoutError:
                msg = f"Node '{node_name}' timed out after {NODE_TIMEOUT}s."
                print(f"\n[TIMEOUT] {msg}")
                telemetry.log_output(node_name, f"\n[TIMEOUT] {msg}\n")
                telemetry.log_status(node_name, "failed")
                return self._handle_error(state, node_name, msg)
            except Exception as e:
                error_trace = traceback.format_exc()
                msg = f"Node '{node_name}' failed with error: {str(e)}"
                print(f"\n[ERROR] {msg}")
                telemetry.log_output(node_name, f"\n[ERROR] {msg}\n{error_trace}\n")
                telemetry.log_status(node_name, "failed")
                return self._handle_error(state, node_name, msg, error_trace)

        return wrapper

    def _handle_error(
        self, state: AgentState, node_name: str, msg: str, trace: str | None = None
    ):
        """Handles node errors by updating state and retry counts."""
        retry_count = state.get("retry_count", 0) + 1
        last_error = msg
        if trace:
            last_error += f"\n{trace}"

        if node_name == "tester":
            return {
                "test_output": f"FAIL: {msg}",
                "retry_count": retry_count,
                "last_error": last_error,
            }

        response = {
            "retry_count": retry_count,
            "messages": [SystemMessage(content=msg)],
            "last_error": last_error,
        }

        if node_name == "reviewer":
            response["review_status"] = "error"
        elif node_name == "pr_creator":
            response["review_status"] = "pr_failed"
        elif node_name == "coder":
            response["code_status"] = "failed"
            response["review_status"] = "rejected"

        return response

    async def verify_environment(self) -> bool:
        """Verifies that the necessary CLI tools are installed."""
        tools = ["git", "gh", "gemini"]
        for tool in tools:
            try:
                res = await run_command(tool, ["--version"])
                if res["exit_code"] != 0:
                    print(f"Error: {tool} is not working correctly.")
                    return False
            except Exception:
                print(f"Error: {tool} is not installed or not in PATH.")
                return False
        return True

    async def run(self, input_prompt: str, initial_state: dict | None = None):
        """Run the workflow with the given prompt."""
        if not await self.verify_environment():
            return {"error": "Environment verification failed."}

        telemetry = get_telemetry()
        issue_match = re.search(r"https://github\.com/[^\s]+/issues/\d+", input_prompt)

        if not self.start_node:
            self.start_node = "coder"

        print(f"Starting workflow at node: {self.start_node}")
        telemetry.log_workflow_status("running")
        telemetry.log_status(self.start_node, "active")
        telemetry.log_output(
            self.start_node, f"INIT: Starting workflow with prompt: {input_prompt}"
        )

        if not self.graph:
            self.graph = create_graph(self._wrap_node, self.start_node)

        initial_commit_hash = ""
        if os.path.exists(".git"):
            try:
                initial_commit_hash = await get_head()
                msg = f"Initial commit hash: {initial_commit_hash}\n"
                telemetry.log_output(self.start_node, msg)
                print(msg, end="")
            except Exception as e:
                msg = f"Warning: Failed to capture initial commit hash: {e}\n"
                telemetry.log_output(self.start_node, msg)
                print(msg, end="")

        # Ensure existing tests run successfully if starting from coder
        if self.start_node == "coder":
            msg = "Verifying baseline tests...\n"
            telemetry.log_output(self.start_node, msg)
            print(msg, end="")
            test_cmd, test_args = get_test_command()
            try:
                msg = f"Running {test_cmd} {' '.join(test_args)}...\n"
                telemetry.log_output(self.start_node, msg)
                print(msg, end="")
                res = await run_command(test_cmd, test_args, node=self.start_node)
                if res["exit_code"] != 0:
                    msg = "Warning: Baseline tests failed. Proceeding anyway, but be aware.\n"
                    telemetry.log_output(self.start_node, msg)
                    print(msg, end="")
                else:
                    msg = "Baseline tests passed.\n"
                    telemetry.log_output(self.start_node, msg)
                    print(msg, end="")
            except Exception as e:
                msg = f"Warning: Could not run baseline tests: {e}\n"
                telemetry.log_output(self.start_node, msg)
                print(msg, end="")

        # Build default initial state
        default_state = {
            "messages": [HumanMessage(content=input_prompt)],
            "retry_count": 0,
            "issue_url": issue_match.group(0) if issue_match else "",
            "test_output": ""
            if self.start_node not in ["reviewer", "pr_creator"]
            else "",
            "code_status": "pending",
            "review_status": "approved"
            if self.start_node == "pr_creator"
            else "pending",
            "pr_url": "",
            "initial_commit_hash": initial_commit_hash,
            "git_diff": "",
            "verbose": self.verbose,
            "last_error": "",
        }

        # Merge reconstructed state if provided
        if initial_state:
            print(f"Merging reconstructed state: {initial_state}")
            for key, value in initial_state.items():
                if key != "prompt":
                    default_state[key] = value

        return await self.graph.ainvoke(default_state)
