from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from copium_loop.engine.base import LLMEngine


class AgentState(TypedDict):
    """The state of the workflow."""

    messages: Annotated[list[BaseMessage], add_messages]
    engine: LLMEngine
    code_status: str
    test_output: str
    review_status: str
    architect_status: str
    retry_count: int
    pr_url: str
    issue_url: str
    initial_commit_hash: str
    git_diff: str
    verbose: bool
    last_error: str
    journal_status: str
    head_hash: str
    has_changeset: bool
