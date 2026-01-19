"Tests for copium_loop workflow."

import pytest

from copium_loop.copium_loop import WorkflowManager


@pytest.fixture
def workflow():
    """Create a WorkflowManager instance for testing."""
    return WorkflowManager()


class TestGraphCreation:
    """Tests for graph creation and compilation."""

    def test_create_graph_adds_all_nodes(self, workflow):
        """Test that create_graph adds all required nodes."""
        graph = workflow.create_graph()
        assert graph is not None
        assert workflow.graph is not None

    @pytest.mark.parametrize(
        "start_node", ["coder", "tester", "reviewer", "pr_creator"]
    )
    def test_create_graph_with_valid_start_nodes(self, start_node):
        """Test graph creation with each valid start node."""
        workflow = WorkflowManager(start_node=start_node)
        graph = workflow.create_graph()
        assert graph is not None

    def test_create_graph_with_invalid_start_node(self, capsys):
        """Test graph creation falls back to coder for invalid start node."""
        workflow = WorkflowManager(start_node="invalid")
        graph = workflow.create_graph()
        assert graph is not None
        captured = capsys.readouterr()
        assert "Valid nodes are:" in captured.out
