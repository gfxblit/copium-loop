from unittest.mock import MagicMock, patch

from copium_loop.copium_loop import WorkflowManager


def test_workflow_manager_start_node_journaler():
    """Test that WorkflowManager accepts 'journaler' as a start node."""
    manager = WorkflowManager(start_node="journaler")

    # Capture stdout to check for warning
    import io
    import sys
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        # We expect this might fail due to LangGraph dependencies or what not,
        # but the check we care about happens before graph compilation usually.
        # However, create_graph actually calls compile().
        # Let's mock create_graph inside copium_loop.py to avoid running the real one
        # but checking the valid_nodes logic in WorkflowManager.
        with patch('copium_loop.copium_loop.create_graph') as mock_create_graph:
            manager.create_graph()

            # If the logic in WorkflowManager passes, it should call create_graph with "journaler"
            mock_create_graph.assert_called_with(manager._wrap_node, "journaler")

    finally:
        sys.stdout = sys.__stdout__

    output = captured_output.getvalue()

    # It should NOT print warning
    assert "Warning: Invalid start node \"journaler\"" not in output
    assert "Falling back to \"coder\"" not in output

def test_graph_entry_point_logic():
    """Test the logic in graph.py regarding entry node."""
    # We can test this by importing create_graph from copium_loop.graph
    # and mocking StateGraph and checking add_edge calls.

    with patch('copium_loop.graph.StateGraph') as mock_state_graph_cls:
        mock_graph = MagicMock()
        mock_state_graph_cls.return_value = mock_graph

        # Mock compile return value
        mock_graph.compile.return_value = "compiled_graph"

        # Mock wrap_node_func
        wrap = MagicMock()

        from copium_loop.graph import START, create_graph

        # Test with journaler
        create_graph(wrap, start_node="journaler")

        # Verify add_edge was called with START -> journaler
        mock_graph.add_edge.assert_any_call(START, "journaler")

        # Reset mocks
        mock_graph.reset_mock()

        # Test with invalid node
        create_graph(wrap, start_node="invalid_node")

        # Verify add_edge was called with START -> coder (fallback)
        mock_graph.add_edge.assert_any_call(START, "coder")
