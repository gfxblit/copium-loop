"Core workflow implementation."

import asyncio
import re
import traceback
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.constants import NODE_TIMEOUT, VALID_NODES
from copium_loop.discovery import get_test_command
from copium_loop.engine.base import LLMEngine
from copium_loop.engine.factory import get_engine
from copium_loop.git import get_current_branch, get_head, is_git_repo, resolve_ref
from copium_loop.graph import create_graph
from copium_loop.notifications import notify
from copium_loop.session_manager import SessionManager
from copium_loop.shell import run_command
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


class WorkflowManager:
    """
    Manages the TDD development workflow using LangGraph and Gemini.
    Orchestrates the coding, testing, and review phases.
    """

    _environment_verified = False

    def __init__(
        self,
        start_node: str | None = None,
        verbose: bool = False,
        engine_name: str | None = None,
        session_id: str | None = None,
    ):
        self.graph = None
        self.start_node = start_node
        self.verbose = verbose
        self.engine_name = engine_name
        self.session_id = session_id
        self.engine: LLMEngine | None = None
        self.session_manager: SessionManager | None = None

    async def notify(self, title: str, message: str, priority: int = 3):
        """Sends a notification to ntfy.sh if NTFY_CHANNEL is set."""
        await notify(title, message, priority)

    def create_graph(self):
        """Creates and compiles the workflow graph."""
        if self.start_node and self.start_node not in VALID_NODES:
            print(f'Warning: Invalid start node "{self.start_node}".')
            print(f"Valid nodes are: {', '.join(VALID_NODES)}")
            print('Falling back to "coder".')
        self.graph = create_graph(self._wrap_node, self.start_node)
        return self.graph

    def _wrap_node(self, node_name: str, node_func):
        """Wraps a node function with a timeout and error handling."""

        async def wrapper(state: AgentState):
            telemetry = get_telemetry()
            # Refresh head_hash before node execution for cache-busting accuracy
            try:
                state["head_hash"] = await get_head(node=node_name)
            except Exception:
                state["head_hash"] = "unknown"

            try:
                result = await asyncio.wait_for(node_func(state), timeout=NODE_TIMEOUT)
                self._persist_state(state, result)
                return result
            except asyncio.TimeoutError:
                msg = f"Node '{node_name}' timed out after {NODE_TIMEOUT}s."
                print(f"\n[TIMEOUT] {msg}")
                telemetry.log_info(node_name, f"\n[TIMEOUT] {msg}\n")
                telemetry.log_status(node_name, "failed")
                result = self._handle_error(state, node_name, msg)
                self._persist_state(state, result)
                return result
            except Exception as e:
                error_trace = traceback.format_exc()
                msg = f"Node '{node_name}' failed with error: {str(e)}"
                print(f"\n[ERROR] {msg}")
                telemetry.log_info(node_name, f"\n[ERROR] {msg}\n{error_trace}\n")
                telemetry.log_status(node_name, "failed")
                result = self._handle_error(state, node_name, msg, error_trace)
                self._persist_state(state, result)
                return result

        return wrapper

    def _persist_state(self, state: AgentState, result: Any):
        """Persists the agent state to the session manager."""
        if self.session_manager:
            # Merge result into state to persist the full updated state
            updated_state = state.copy()
            if isinstance(result, dict):
                updated_state.update(result)

            # Remove non-serializable objects like the engine
            serializable_state = {
                k: v
                for k, v in updated_state.items()
                if k not in ["engine", "messages"]
            }
            self.session_manager.update_agent_state(serializable_state)

    def _handle_error(
        self, state: AgentState, node_name: str, msg: str, trace: str | None = None
    ):
        """Handles node errors by updating state and retry counts."""
        from copium_loop.nodes.utils import is_infrastructure_error

        if is_infrastructure_error(msg):
            print(
                f"\n[INFRA ERROR] Transient failure detected in {node_name}. Retrying..."
            )

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
        elif node_name == "architect":
            response["architect_status"] = "error"
        elif node_name in ["pr_creator", "pr_pre_checker"]:
            response["review_status"] = "pr_failed"
        elif node_name == "coder":
            response["code_status"] = "failed"

        return response

    async def verify_environment(self, engine: LLMEngine) -> bool:
        """Verifies that the necessary CLI tools are installed."""
        if WorkflowManager._environment_verified:
            return True

        tools = ["git", "gh"] + engine.get_required_tools()

        for tool in tools:
            try:
                res = await run_command(tool, ["--version"])
                if res["exit_code"] != 0:
                    print(f"Error: {tool} is not working correctly.")
                    return False
            except Exception:
                print(f"Error: {tool} is not installed or not in PATH.")
                return False

        WorkflowManager._environment_verified = True
        return True

    async def run(self, input_prompt: str, initial_state: dict | None = None):
        """Run the workflow with the given prompt."""
        if self.start_node and self.start_node not in VALID_NODES:
            raise ValueError(
                f"Invalid start node: {self.start_node}. Valid nodes are: {', '.join(VALID_NODES)}"
            )

        # Initialize telemetry and session manager
        telemetry = get_telemetry()
        if not self.session_id:
            self.session_id = telemetry.session_id

        self.session_manager = SessionManager(self.session_id)

        # Store sticky environment metadata
        if await is_git_repo(node=self.start_node):
            try:
                branch = await get_current_branch(node=self.start_node)

                res = await run_command(
                    "git", ["rev-parse", "--show-toplevel"], node=self.start_node
                )
                repo_root = res["output"].strip() if res["exit_code"] == 0 else None

                self.session_manager.update_session_info(
                    branch_name=branch,
                    repo_root=repo_root,
                    engine_name=self.engine_name,
                    original_prompt=input_prompt,
                )
            except Exception:
                pass
        elif self.engine_name:
            self.session_manager.update_session_info(
                engine_name=self.engine_name, original_prompt=input_prompt
            )

        # Determine engine
        self.engine = get_engine(self.engine_name)
        if initial_state and "engine" in initial_state and self.engine_name is None:
            self.engine = initial_state["engine"]

        if self.session_manager:
            self.engine.set_session_manager(self.session_manager)

        if not await self.verify_environment(self.engine):
            return {"error": "Environment verification failed."}

        issue_match = re.search(r"https://github\.com/[^\s]+/issues/\d+", input_prompt)

        if not self.start_node:
            self.start_node = "coder"

        print(f"Starting workflow at node: {self.start_node}")
        telemetry.log_workflow_status("running")
        telemetry.log_status(self.start_node, "active")
        telemetry.log_info(
            self.start_node, f"INIT: Starting workflow with prompt: {input_prompt}"
        )

        if not self.graph:
            self.graph = create_graph(self._wrap_node, self.start_node)

        initial_commit_hash = ""
        if await is_git_repo(node=self.start_node):
            try:
                # Use a common base branch for architect and reviewer to get meaningful diffs
                if self.start_node in ["architect", "reviewer"]:
                    current_branch = await get_current_branch(node=self.start_node)
                    base_refs = ["origin/main", "main", "origin/master", "master"]

                    # If we are on a base branch, don't use it as the diff base
                    if current_branch in base_refs:
                        base_refs = [r for r in base_refs if r != current_branch]
                    if f"origin/{current_branch}" in base_refs:
                        base_refs = [
                            r for r in base_refs if r != f"origin/{current_branch}"
                        ]

                    base_hash = None
                    used_ref = None

                    for ref in base_refs:
                        base_hash = await resolve_ref(ref=ref, node=self.start_node)
                        if base_hash:
                            used_ref = ref
                            break

                    if base_hash:
                        initial_commit_hash = base_hash
                        msg = f"Using {used_ref} as diff base: {initial_commit_hash}\n"
                    else:
                        initial_commit_hash = await get_head(node=self.start_node)
                        msg = f"No common base branch found, using HEAD as diff base: {initial_commit_hash}\n"
                else:
                    initial_commit_hash = await get_head(node=self.start_node)
                    msg = f"Initial commit hash: {initial_commit_hash}\n"

                telemetry.log_info(self.start_node, msg)
                print(msg, end="")
            except Exception as e:
                msg = f"Warning: Failed to capture initial commit hash: {e}\n"
                telemetry.log_info(self.start_node, msg)
                print(msg, end="")

        # Ensure existing tests run successfully if starting from coder
        if self.start_node == "coder":
            msg = "Verifying baseline tests...\n"
            telemetry.log_info(self.start_node, msg)
            print(msg, end="")
            test_cmd, test_args = get_test_command()
            try:
                msg = f"Running {test_cmd} {' '.join(test_args)}...\n"
                telemetry.log_info(self.start_node, msg)
                print(msg, end="")
                res = await run_command(test_cmd, test_args, node=self.start_node)
                if res["exit_code"] != 0:
                    msg = "Warning: Baseline tests failed. Proceeding anyway, but be aware.\n"
                    telemetry.log_info(self.start_node, msg)
                    print(msg, end="")
                else:
                    msg = "Baseline tests passed.\n"
                    telemetry.log_info(self.start_node, msg)
                    print(msg, end="")
            except Exception as e:
                msg = f"Warning: Could not run baseline tests: {e}\n"
                telemetry.log_info(self.start_node, msg)
                print(msg, end="")

        try:
            current_head_hash = await get_head(node=self.start_node)
        except Exception:
            current_head_hash = ""

        # Build default initial state
        default_state = {
            "messages": [HumanMessage(content=input_prompt)],
            "engine": self.engine,
            "retry_count": 0,
            "issue_url": issue_match.group(0) if issue_match else "",
            "test_output": ""
            if self.start_node not in ["reviewer", "pr_pre_checker", "pr_creator"]
            else "",
            "code_status": "pending",
            "review_status": "approved"
            if self.start_node in ["pr_pre_checker", "pr_creator"]
            else "pending",
            "architect_status": "pending",
            "pr_url": "",
            "initial_commit_hash": initial_commit_hash,
            "head_hash": current_head_hash,
            "git_diff": "",
            "verbose": self.verbose,
            "last_error": "",
            "journal_status": "pending",
        }

        # Merge reconstructed state if provided
        if initial_state:
            print(f"Merging reconstructed state: {initial_state}")
            for key, value in initial_state.items():
                if key != "prompt" and key != "engine":
                    default_state[key] = value

        return await self.graph.ainvoke(default_state)
