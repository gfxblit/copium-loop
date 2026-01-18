"""Core workflow implementation."""

import re
from typing import Optional
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

from copium_loop.state import AgentState
from copium_loop.nodes import (
    coder, tester, reviewer, pr_creator,
    should_continue_from_test, should_continue_from_review, should_continue_from_pr_creator
)
from copium_loop.utils import notify

class WorkflowManager:
    """
    Manages the TDD development workflow using LangGraph and Gemini.
    Orchestrates the coding, testing, and review phases.
    """

    def __init__(self, start_node: Optional[str] = None, verbose: bool = False):
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
        workflow.add_node('coder', coder)
        workflow.add_node('tester', tester)
        workflow.add_node('reviewer', reviewer)
        workflow.add_node('pr_creator', pr_creator)

        # Determine entry point
        valid_nodes = ['coder', 'tester', 'reviewer', 'pr_creator']
        entry_node = self.start_node if self.start_node in valid_nodes else 'coder'
        
        if self.start_node and self.start_node not in valid_nodes:
            print(f"Warning: Invalid start node \"{self.start_node}\".")
            print(f"Valid nodes are: {', '.join(valid_nodes)}")
            print('Falling back to "coder".')

        # Edges
        workflow.add_edge(START, entry_node)
        workflow.add_edge('coder', 'tester')

        workflow.add_conditional_edges(
            'tester',
            should_continue_from_test,
            {
                'reviewer': 'reviewer',
                'coder': 'coder',
                END: END
            }
        )

        workflow.add_conditional_edges(
            'reviewer',
            should_continue_from_review,
            {
                'pr_creator': 'pr_creator',
                'coder': 'coder',
                END: END
            }
        )

        workflow.add_conditional_edges(
            'pr_creator',
            should_continue_from_pr_creator,
            {
                END: END,
                'coder': 'coder'
            }
        )

        self.graph = workflow.compile()
        return self.graph

    async def run(self, input_prompt: str):
        """Run the workflow with the given prompt."""
        issue_match = re.search(r'https://github\.com/[^\s]+/issues/\d+', input_prompt)
        
        if not self.start_node:
            self.start_node = 'coder'
        
        print(f"Starting workflow at node: {self.start_node}")

        if not self.graph:
            self.create_graph()

        initial_state = {
            'messages': [HumanMessage(content=input_prompt)],
            'retry_count': 0,
            'issue_url': issue_match.group(0) if issue_match else '',
            'test_output': '' if self.start_node not in ['reviewer', 'pr_creator'] else '',
            'code_status': 'pending',
            'review_status': 'approved' if self.start_node == 'pr_creator' else 'pending',
            'pr_url': '',
            'verbose': self.verbose
        }
        
        return await self.graph.ainvoke(initial_state)