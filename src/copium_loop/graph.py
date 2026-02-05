from langgraph.graph import END, START, StateGraph

from copium_loop.constants import VALID_NODES
from copium_loop.nodes import (
    architect,
    coder,
    journaler,
    pr_creator,
    pr_pre_checker,
    reviewer,
    should_continue_from_architect,
    should_continue_from_journaler,
    should_continue_from_pr_creator,
    should_continue_from_pr_pre_checker,
    should_continue_from_review,
    should_continue_from_test,
    tester,
)
from copium_loop.state import AgentState


def create_graph(wrap_node_func, start_node: str | None = None):
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("coder", wrap_node_func("coder", coder))
    workflow.add_node("tester", wrap_node_func("tester", tester))
    workflow.add_node("architect", wrap_node_func("architect", architect))
    workflow.add_node("reviewer", wrap_node_func("reviewer", reviewer))
    workflow.add_node("pr_pre_checker", wrap_node_func("pr_pre_checker", pr_pre_checker))
    workflow.add_node("pr_creator", wrap_node_func("pr_creator", pr_creator))
    workflow.add_node("journaler", wrap_node_func("journaler", journaler))

    # Determine entry point
    entry_node = start_node if start_node in VALID_NODES else "coder"

    # Edges
    workflow.add_edge(START, entry_node)
    workflow.add_edge("coder", "tester")

    workflow.add_conditional_edges(
        "tester",
        should_continue_from_test,
        {"architect": "architect", "coder": "coder", END: END},
    )

    workflow.add_conditional_edges(
        "architect",
        should_continue_from_architect,
        {"reviewer": "reviewer", "coder": "coder", "architect": "architect", END: END},
    )

    workflow.add_conditional_edges(
        "reviewer",
        should_continue_from_review,
        {
            "pr_pre_checker": "pr_pre_checker",
            "coder": "coder",
            "reviewer": "reviewer",
            "pr_failed": END,
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "pr_pre_checker",
        should_continue_from_pr_pre_checker,
        {"pr_creator": "pr_creator", "coder": "coder", END: END},
    )

    workflow.add_conditional_edges(
        "journaler",
        should_continue_from_journaler,
        {"pr_creator": "pr_creator", END: END},
    )

    workflow.add_conditional_edges(
        "pr_creator",
        should_continue_from_pr_creator,
        {"coder": "coder", END: END},
    )

    return workflow.compile()
