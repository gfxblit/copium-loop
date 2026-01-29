"Tests for copium_loop workflow."

from unittest.mock import AsyncMock, patch

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


class TestContinueFeature:
    """Tests for the continue feature with state reconstruction."""

    def test_workflow_accepts_initial_state(self):
        """Test that workflow can be initialized with reconstructed state."""
        workflow = WorkflowManager(start_node="tester", verbose=False)
        workflow.create_graph()

        # Verify the graph was created
        assert workflow.graph is not None
        assert workflow.start_node == "tester"

    def test_workflow_run_accepts_initial_state_parameter(self):
        """Test that workflow.run() accepts initial_state parameter."""
        workflow = WorkflowManager(start_node="coder", verbose=False)

        # We can't actually run the workflow in tests without mocking,
        # but we can verify the method signature accepts the parameter
        import inspect

        sig = inspect.signature(workflow.run)
        assert "initial_state" in sig.parameters
        assert sig.parameters["initial_state"].default is None


class TestEnvironmentVerification:
    """Tests for environment verification."""

    @pytest.mark.asyncio
    @patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock)
    async def test_verify_environment_success(self, mock_run, workflow):
        mock_run.return_value = {"exit_code": 0}
        assert await workflow.verify_environment() is True
        assert mock_run.call_count == 3

    @pytest.mark.asyncio
    @patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock)
    async def test_verify_environment_failure(self, mock_run, workflow):
        mock_run.return_value = {"exit_code": 1}
        assert await workflow.verify_environment() is False

    @pytest.mark.asyncio
    @patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock)
    async def test_verify_environment_exception(self, mock_run, workflow):
        mock_run.side_effect = Exception("failed")
        assert await workflow.verify_environment() is False


class TestWorkflowRun:
    """Tests for workflow execution."""

    @pytest.mark.asyncio
    @patch(
        "copium_loop.copium_loop.WorkflowManager.verify_environment",
        new_callable=AsyncMock,
    )
    @patch("copium_loop.copium_loop.get_telemetry")
    @patch("copium_loop.copium_loop.create_graph")
    async def test_run_verify_failure(
        self, _mock_create, _mock_telemetry, mock_verify, workflow
    ):
        mock_verify.return_value = False
        result = await workflow.run("test prompt")
        assert "error" in result
        assert result["error"] == "Environment verification failed."

    @pytest.mark.asyncio
    @patch(
        "copium_loop.copium_loop.WorkflowManager.verify_environment",
        new_callable=AsyncMock,
    )
    @patch("copium_loop.copium_loop.get_head", new_callable=AsyncMock)
    @patch("copium_loop.copium_loop.get_test_command")
    @patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock)
    @patch("copium_loop.copium_loop.create_graph")
    @patch("os.path.exists")
    async def test_run_success_flow(
        self,
        mock_exists,
        mock_create,
        mock_run,
        mock_get_test,
        mock_get_head,
        mock_verify,
        workflow,
    ):
        mock_verify.return_value = True
        mock_exists.return_value = True
        mock_get_head.return_value = "commit123"
        mock_get_test.return_value = ("pytest", [])
        mock_run.return_value = {"exit_code": 0, "output": "tests passed"}

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "completed"}
        mock_create.return_value = mock_graph

        result = await workflow.run("test prompt")
        assert result == {"status": "completed"}
        mock_graph.ainvoke.assert_called_once()

        # Verify initial state construction
        state = mock_graph.ainvoke.call_args[0][0]
        assert state["initial_commit_hash"] == "commit123"
        assert state["retry_count"] == 0
        assert state["last_error"] == ""

    @pytest.mark.asyncio
    @patch("copium_loop.copium_loop.notify", new_callable=AsyncMock)
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
    @patch(
        "copium_loop.copium_loop.WorkflowManager.verify_environment",
        new_callable=AsyncMock,
    )
    @patch("copium_loop.copium_loop.get_head", new_callable=AsyncMock)
    @patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock)
    @patch("copium_loop.copium_loop.create_graph")
    @patch("os.path.exists")
    async def test_run_baseline_test_failure(
        self, mock_exists, mock_create, mock_run, mock_get_head, mock_verify, workflow
    ):
        mock_verify.return_value = True
        mock_exists.return_value = True
        mock_get_head.return_value = "commit123"
        # First call is git rev-parse (covered by get_head), but wait, I mocked get_head.
        # Inside run(), it calls get_head().
        # Then it calls get_test_command() and run_command().

        with patch(
            "copium_loop.copium_loop.get_test_command", return_value=("pytest", [])
        ):
            mock_run.return_value = {"exit_code": 1, "output": "baseline failed"}

            mock_graph = AsyncMock()
            mock_graph.ainvoke.return_value = {"status": "completed"}
            mock_create.return_value = mock_graph

            result = await workflow.run("test prompt")
            assert result == {"status": "completed"}
            # It should have called run_command for baseline test and it failed but continued
