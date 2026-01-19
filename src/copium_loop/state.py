from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """The state of the workflow."""
    messages: Annotated[List[BaseMessage], add_messages]
    code_status: str
    test_output: str
    review_status: str
    retry_count: int
    pr_url: str
    issue_url: str
    initial_commit_hash: str
    git_diff: str
    verbose: bool
