"Tests for copium_loop workflow."

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph

from copium_loop.graph import START, create_graph


@pytest.fixture
def workflow(workflow_manager_factory):
    """Create a WorkflowManager instance for testing."""
    return workflow_manager_factory()


class TestGraphCreation:
    """Tests for graph creation and compilation."""

    def test_create_graph_adds_all_nodes(self, workflow):
        """Test that create_graph adds all required nodes."""
        graph = workflow.create_graph()
        assert graph is not None
        assert workflow.graph is not None

    def test_create_graph_standalone(self):
        """Test standalone graph creation."""
        graph = create_graph(lambda _name, func: func)
        assert isinstance(graph, CompiledStateGraph)
        # Check that it has the expected nodes
        assert "coder" in graph.nodes
        assert "tester" in graph.nodes
        assert "architect" in graph.nodes
        assert "reviewer" in graph.nodes
        assert "pr_creator" in graph.nodes

    @pytest.mark.parametrize(
        "start_node",
        ["coder", "tester", "architect", "reviewer", "pr_creator", "journaler"],
    )
    def test_create_graph_with_valid_start_nodes(
        self, workflow_manager_factory, start_node
    ):
        """Test graph creation with each valid start node."""
        workflow = workflow_manager_factory(start_node=start_node)
        graph = workflow.create_graph()
        assert graph is not None

    def test_graph_entry_point_logic(self):
        """Test the logic in graph.py regarding entry node."""
        from unittest.mock import MagicMock

        with patch("copium_loop.graph.StateGraph") as mock_state_graph_cls:
            mock_graph = MagicMock()
            mock_state_graph_cls.return_value = mock_graph

            # Mock compile return value
            mock_graph.compile.return_value = "compiled_graph"

            # Mock wrap_node_func
            wrap = MagicMock()

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

    def test_create_graph_with_invalid_start_node(self, workflow_manager_factory, capsys):
        """Test graph creation falls back to coder for invalid start node."""
        workflow = workflow_manager_factory(start_node="invalid")
        graph = workflow.create_graph()
        assert graph is not None
        captured = capsys.readouterr()
        assert "Valid nodes are:" in captured.out


class TestContinueFeature:
    """Tests for the continue feature with state reconstruction."""

    def test_workflow_accepts_initial_state(self, workflow_manager_factory):
        """Test that workflow can be initialized with reconstructed state."""
        workflow = workflow_manager_factory(start_node="tester", verbose=False)
        workflow.create_graph()

        # Verify the graph was created
        assert workflow.graph is not None
        assert workflow.start_node == "tester"

    def test_workflow_run_accepts_initial_state_parameter(self, workflow_manager_factory):
        """Test that workflow.run() accepts initial_state parameter."""
        workflow = workflow_manager_factory(start_node="coder", verbose=False)

        # We can't actually run the workflow in tests without mocking,
        # but we can verify the method signature accepts the parameter
        import inspect

        sig = inspect.signature(workflow.run)
        assert "initial_state" in sig.parameters
        assert sig.parameters["initial_state"].default is None


class TestEnvironmentVerification:
    """Tests for environment verification."""

    @pytest.mark.asyncio
    async def test_verify_environment_success(self, mock_run_command, workflow):
        mock_run_command.return_value = {"exit_code": 0}
        assert await workflow.verify_environment() is True
        assert mock_run_command.call_count == 3

    @pytest.mark.asyncio
    async def test_verify_environment_failure(self, mock_run_command, workflow):
        mock_run_command.return_value = {"exit_code": 1}
        assert await workflow.verify_environment() is False

    @pytest.mark.asyncio
    async def test_verify_environment_exception(self, mock_run_command, workflow):
        mock_run_command.side_effect = Exception("failed")
        assert await workflow.verify_environment() is False


class TestWorkflowRun:
    """Tests for workflow execution."""

    @pytest.mark.asyncio
    async def test_run_verify_failure(
        self, mock_verify_environment, workflow
    ):
        mock_verify_environment.return_value = False
        result = await workflow.run("test prompt")
        assert "error" in result
        assert result["error"] == "Environment verification failed."

    @pytest.mark.asyncio
    async def test_run_success_flow(
        self,
        mock_os_path_exists,
        mock_create_graph,
        mock_run_command,
        mock_get_test_command,
        mock_get_head,
        mock_verify_environment,
        workflow,
    ):
        mock_verify_environment.return_value = True
        mock_os_path_exists.return_value = True
        mock_get_head.return_value = "commit123"
        mock_get_test_command.return_value = ("pytest", [])
        mock_run_command.return_value = {"exit_code": 0, "output": "tests passed"}

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "completed"}
        mock_create_graph.return_value = mock_graph

        result = await workflow.run("test prompt")
        assert result == {"status": "completed"}
        mock_graph.ainvoke.assert_called_once()

        # Verify initial state construction
        state = mock_graph.ainvoke.call_args[0][0]
        assert state["initial_commit_hash"] == "commit123"
        assert state["retry_count"] == 0
        assert state["last_error"] == ""

    @pytest.mark.asyncio
    async def test_notify_wrapper(self, mock_notify, workflow):
        await workflow.notify("title", "message")
        mock_notify.assert_called_with("title", "message", 3)

    @pytest.mark.asyncio
    async def test_wrap_node_exception_handling(self, workflow):
        async def failing_node(_state):
            raise ValueError("node failed")

        wrapped = workflow._wrap_node("coder", failing_node)
        result = await wrapped({"retry_count": 0})

        assert result["code_status"] == "failed"
        assert "ValueError: node failed" in result["last_error"]

    @pytest.mark.asyncio
    async def test_run_baseline_test_failure(
        self, mock_os_path_exists, mock_create_graph, mock_run_command, mock_get_head, mock_verify_environment, mock_get_test_command, workflow
    ):
        mock_verify_environment.return_value = True
        mock_os_path_exists.return_value = True
        mock_get_head.return_value = "commit123"
        mock_get_test_command.return_value = ("pytest", [])
        mock_run_command.return_value = {"exit_code": 1, "output": "baseline failed"}

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "completed"}
        mock_create_graph.return_value = mock_graph

        result = await workflow.run("test prompt")
        assert result == {"status": "completed"}

    @pytest.mark.asyncio
    async def test_run_baseline_test_exception(
        self, mock_os_path_exists, mock_create_graph, mock_get_head, mock_verify_environment, mock_get_test_command, mock_run_command, workflow
    ):
        mock_verify_environment.return_value = True
        mock_os_path_exists.return_value = True
        mock_get_head.return_value = "commit123"
        mock_get_test_command.return_value = ("pytest", [])
        mock_run_command.side_effect = Exception("baseline error")

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "completed"}
        mock_create_graph.return_value = mock_graph

        result = await workflow.run("test prompt")
        assert result == {"status": "completed"}

    @pytest.mark.asyncio
    async def test_run_get_head_exception(
        self, mock_os_path_exists, mock_create_graph, mock_get_head, mock_verify_environment, workflow
    ):
        mock_verify_environment.return_value = True
        mock_os_path_exists.return_value = True
        mock_get_head.side_effect = Exception("git error") # This was previously inline patch, moved to fixture setup in this example.

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "completed"}
        mock_create_graph.return_value = mock_graph

        result = await workflow.run("test prompt")
        assert result == {"status": "completed"}

    @pytest.mark.asyncio
    async def test_run_with_initial_state(
        self, mock_os_path_exists, mock_create_graph, mock_get_head, mock_verify_environment, workflow
    ):
        mock_verify_environment.return_value = True
        mock_os_path_exists.return_value = True
        mock_get_head.return_value = "commit123"
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "completed"}
        mock_create_graph.return_value = mock_graph

        initial_state = {"retry_count": 5, "code_status": "coded"}
        result = await workflow.run("test prompt", initial_state=initial_state)

        assert result == {"status": "completed"}
        state = mock_graph.ainvoke.call_args[0][0]
        assert state["retry_count"] == 5
        assert state["code_status"] == "coded"
        assert state["initial_commit_hash"] == "commit123"


class TestNodeTimeouts:
    """Tests for node timeout handling using parameterization."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "node_name, expected_output_key, expected_output_value_part, expected_status_key, expected_status_value",
        [
            ("tester", "test_output", "FAIL: Node 'tester' timed out", None, None),
            ("coder", "last_error", "Node 'coder' timed out", "code_status", "failed"),
            ("architect", "messages", "Node 'architect' timed out", "architect_status", "error"),
            ("reviewer", "messages", "Node 'reviewer' timed out", "review_status", "error"),
            ("pr_creator", "messages", "Node 'pr_creator' timed out", "review_status", "pr_failed"),
            ("unknown_node", "last_error", "Node 'unknown_node' timed out", None, None),
        ],
    )
    async def test_node_timeout_scenarios(
        self,
        workflow_manager_factory,
        node_name,
        expected_output_key,
        expected_output_value_part,
        expected_status_key,
        expected_status_value,
    ):
        """Test that nodes time out and update state accordingly."""

        async def slow_node(_state):
            await asyncio.sleep(2)  # Simulate a node taking too long
            return {"arbitrary_key": "arbitrary_value"} # Return something to be overridden

        manager = workflow_manager_factory()
        with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):  # Set a short timeout
            wrapped = manager._wrap_node(node_name, slow_node)
            state = {"retry_count": 0}
            result = await wrapped(state)

            assert result["retry_count"] == 1
            if expected_output_key == "messages":
                # For messages, we check if the content contains the expected string
                assert any(expected_output_value_part in msg.content for msg in result.get(expected_output_key, []))
            elif expected_output_key:
                assert expected_output_value_part in result.get(expected_output_key, "")

            if expected_status_key:
                assert result.get(expected_status_key) == expected_status_value

    @pytest.mark.asyncio
    async def test_node_exceeds_inactivity_but_below_node_timeout(self, workflow_manager_factory):
        """
        Test that a node can run longer than INACTIVITY_TIMEOUT if it's below NODE_TIMEOUT.
        This test remains separate as it's not a timeout scenario but a successful execution.
        """
        async def mid_length_node(_state):
            await asyncio.sleep(0.5)
            return {"test_output": "PASS"}

        manager = workflow_manager_factory()
        with patch("copium_loop.copium_loop.NODE_TIMEOUT", 1.0):
            wrapped = manager._wrap_node("mid_length_node", mid_length_node)
            state = {"retry_count": 0}
            result = await wrapped(state)

            assert "test_output" in result
            assert result["test_output"] == "PASS"
            assert result.get("retry_count", 0) == 0

    @pytest.mark.asyncio
    async def test_node_exceeds_node_timeout_specific_assertion(self, workflow_manager_factory):
        """
        Test that a node still times out if it exceeds NODE_TIMEOUT, with a more specific assertion
        for the 'timed out' message as it appears in 'last_error' when no other status is set.
        """
        async def very_slow_node(_state):
            await asyncio.sleep(1.0)
            return {"test_output": "PASS"}

        manager = workflow_manager_factory()
        with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.5):
            wrapped = manager._wrap_node("very_slow_node", very_slow_node)
            state = {"retry_count": 0}
            result = await wrapped(state)

            assert "retry_count" in result
            assert result["retry_count"] == 1
            # Check for the specific timeout message in last_error or other relevant field
            assert "timed out after 0.5s" in result.get("last_error", "") or \
                   "timed out after 0.5s" in result.get("test_output", "")
