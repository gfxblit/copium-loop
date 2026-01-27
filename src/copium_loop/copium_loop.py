"""Core workflow implementation."""

import os
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from copium_loop.nodes import (
    coder,
    pr_creator,
    reviewer,
    should_continue_from_pr_creator,
    should_continue_from_review,
    should_continue_from_test,
    tester,
)
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry
from copium_loop.utils import get_test_command, notify, run_command


class WorkflowManager:
    """
    Manages the TDD development workflow using LangGraph and Gemini.
    Orchestrates the coding, testing, and review phases.
    """

    def __init__(self, start_node: str | None = None, verbose: bool = False):
        self.graph = None
        self.start_node = start_node
        self.verbose = verbose

    # Re-expose notify for external use if needed, or consumers can import it
    async def notify(self, title: str, message: str, priority: int = 3):
        """Sends a notification to ntfy.sh if NTFY_CHANNEL is set."""
        await notify(title, message, priority)

    def create_graph(self):
        workflow = StateGraph(AgentState)

        # Add Nodes
        workflow.add_node("coder", coder)
        workflow.add_node("tester", tester)
        workflow.add_node("reviewer", reviewer)
        workflow.add_node("pr_creator", pr_creator)

        # Determine entry point
        valid_nodes = ["coder", "tester", "reviewer", "pr_creator"]
        entry_node = self.start_node if self.start_node in valid_nodes else "coder"

        if self.start_node and self.start_node not in valid_nodes:
            print(f'Warning: Invalid start node "{self.start_node}".')
            print(f"Valid nodes are: {', '.join(valid_nodes)}")
            print('Falling back to "coder".')

        # Edges
        workflow.add_edge(START, entry_node)
        workflow.add_edge("coder", "tester")

        workflow.add_conditional_edges(
            "tester",
            should_continue_from_test,
            {"reviewer": "reviewer", "coder": "coder", END: END},
        )

        workflow.add_conditional_edges(
            "reviewer",
            should_continue_from_review,
            {
                "pr_creator": "pr_creator",
                "coder": "coder",
                "reviewer": "reviewer",
                END: END,
            },
        )

        workflow.add_conditional_edges(
            "pr_creator", should_continue_from_pr_creator, {END: END, "coder": "coder"}
        )

        self.graph = workflow.compile()
        return self.graph

    async def run(self, input_prompt: str, initial_state: dict | None = None):
        """Run the workflow with the given prompt.

        Args:
            input_prompt: The prompt to run the workflow with
            initial_state: Optional reconstructed state from a previous session
        """
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
            self.create_graph()

        initial_commit_hash = ""
        if os.path.exists(".git"):
            try:
                res = await run_command("git", ["rev-parse", "HEAD"])
                if res["exit_code"] == 0:
                    initial_commit_hash = res["output"].strip()
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
                # We don't necessarily want to fail the whole workflow if baseline tests fail,
                # but we should definitely inform the user.
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
        }

        # Merge reconstructed state if provided
        if initial_state:
            print(f"Merging reconstructed state: {initial_state}")
            # Keep messages from default, but override other fields from reconstructed state
            for key, value in initial_state.items():
                if key != "prompt":  # Don't override with prompt key
                    default_state[key] = value

        return await self.graph.ainvoke(default_state)
