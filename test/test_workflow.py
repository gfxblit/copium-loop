"""Tests for copium_loop workflow."""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from copium_loop.workflow import WorkflowManager, AgentState
from langchain_core.messages import HumanMessage, SystemMessage


@pytest.fixture
def workflow():
    """Create a WorkflowManager instance for testing."""
    return WorkflowManager()


@pytest.fixture
def mock_process():
    """Create a mock asyncio subprocess."""
    mock = MagicMock()
    mock.stdout = AsyncMock()
    mock.stderr = AsyncMock()
    mock.wait = AsyncMock(return_value=0)
    mock.returncode = 0
    return mock


class TestGraphCreation:
    """Tests for graph creation and compilation."""

    def test_create_graph_adds_all_nodes(self, workflow):
        """Test that create_graph adds all required nodes."""
        graph = workflow.create_graph()
        assert graph is not None
        assert workflow.graph is not None

    @pytest.mark.parametrize("start_node", ["coder", "test_runner", "reviewer", "pr_creator"])
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


class TestCoderNode:
    """Tests for the coder node."""

    @pytest.mark.asyncio
    async def test_coder_returns_coded_status(self, workflow):
        """Test that coder node returns coded status."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'Mocked Code Response', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'messages': [HumanMessage(content='Build a login form')]}
            result = await workflow.coder(state)

            assert result['code_status'] == 'coded'
            assert 'Mocked Code Response' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_coder_strips_null_bytes(self, workflow):
        """Test that coder strips null bytes from output."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[
                b'Mocked\x00 Code\x00 Response',
                b''
            ])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'messages': [HumanMessage(content='Build a login form')]}
            result = await workflow.coder(state)

            assert '\x00' not in result['messages'][0].content
            assert result['messages'][0].content == 'Mocked Code Response'

    @pytest.mark.asyncio
    async def test_coder_strips_control_characters(self, workflow):
        """Test that coder strips disruptive control characters."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[
                b'Mocked\x00Code\x07Response\x1B',
                b''
            ])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'messages': [HumanMessage(content='Test')]}
            result = await workflow.coder(state)

            assert result['messages'][0].content == 'MockedCodeResponse'

    @pytest.mark.asyncio
    async def test_coder_preserves_clean_output(self, workflow):
        """Test that coder doesn't modify clean output."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[
                b'Clean response with spaces and\nnewlines.',
                b''
            ])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'messages': [HumanMessage(content='Test')]}
            result = await workflow.coder(state)

            assert result['messages'][0].content == 'Clean response with spaces and\nnewlines.'

    @pytest.mark.asyncio
    async def test_coder_includes_test_failure_in_prompt(self, workflow):
        """Test that coder includes test failure in prompt."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'Fixing...', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {
                'messages': [HumanMessage(content='Fix bug')],
                'test_output': 'FAIL: Expected 1 to be 2'
            }
            await workflow.coder(state)

            # Check that the prompt contains the test failure
            # The prompt is the last positional argument (after 'gemini', '-m', model, '--yolo')
            call_args = mock_exec.call_args[0]
            prompt = call_args[-1]  # Last argument is the prompt
            assert 'Your previous implementation failed tests.' in prompt
            assert 'FAIL: Expected 1 to be 2' in prompt


class TestReviewerNode:
    """Tests for the reviewer node."""

    @pytest.mark.asyncio
    async def test_reviewer_returns_approved(self, workflow):
        """Test that reviewer returns approved status."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'APPROVED', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'test_output': 'PASS', 'retry_count': 0}
            result = await workflow.reviewer(state)

            assert result['review_status'] == 'approved'

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self, workflow):
        """Test that reviewer returns rejected status."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'REJECTED: issues', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'test_output': 'PASS', 'retry_count': 0}
            result = await workflow.reviewer(state)

            assert result['review_status'] == 'rejected'
            assert result['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_reviewer_rejects_on_test_failure(self, workflow):
        """Test that reviewer rejects when tests fail."""
        state = {'test_output': 'FAIL', 'retry_count': 0}
        result = await workflow.reviewer(state)

        assert result['review_status'] == 'rejected'
        assert result['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_reviewer_allows_empty_test_output(self, workflow):
        """Test that reviewer proceeds with empty test output."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'Thinking...\nAPPROVED', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'test_output': '', 'retry_count': 0}
            result = await workflow.reviewer(state)

            assert result['review_status'] == 'approved'


class TestTestRunnerNode:
    """Tests for the test runner node."""

    @pytest.mark.asyncio
    async def test_test_runner_returns_pass(self, workflow):
        """Test that test runner returns PASS on success."""
        with patch.object(workflow, 'run_command') as mock_run:
            mock_run.return_value = {'output': 'All tests passed', 'exit_code': 0}

            state = {'retry_count': 0}
            result = await workflow.test_runner(state)

            assert result['test_output'] == 'PASS'

    @pytest.mark.asyncio
    async def test_test_runner_returns_fail(self, workflow):
        """Test that test runner returns FAIL on failure."""
        with patch.object(workflow, 'run_command') as mock_run:
            mock_run.return_value = {'output': 'FAIL tests', 'exit_code': 1}
            with patch.object(workflow, 'notify') as mock_notify:
                state = {'retry_count': 0}
                result = await workflow.test_runner(state)

                assert 'FAIL' in result['test_output']
                assert result['retry_count'] == 1


class TestPrCreatorNode:
    """Tests for the PR creator node."""

    @pytest.mark.asyncio
    async def test_pr_creator_creates_pr(self, workflow):
        """Test that PR creator creates a PR successfully."""
        with patch.object(workflow, 'run_command') as mock_run:
            mock_run.side_effect = [
                {'output': 'feature-branch\n', 'exit_code': 0},  # branch
                {'output': '', 'exit_code': 0},  # status
                {'output': '', 'exit_code': 0},  # push
                {'output': 'https://github.com/org/repo/pull/1\n', 'exit_code': 0},  # pr
            ]

            state = {'retry_count': 0}
            result = await workflow.pr_creator(state)

            assert result['review_status'] == 'pr_created'
            assert 'PR Created' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_pr_creator_handles_existing_pr(self, workflow):
        """Test that PR creator handles existing PR."""
        with patch.object(workflow, 'run_command') as mock_run:
            mock_run.side_effect = [
                {'output': 'feature-branch\n', 'exit_code': 0},
                {'output': '', 'exit_code': 0},
                {'output': '', 'exit_code': 0},
                {'output': 'already exists: https://github.com/org/repo/pull/1\n', 'exit_code': 1},
            ]

            state = {'retry_count': 0}
            result = await workflow.pr_creator(state)

            assert result['review_status'] == 'pr_created'
            assert 'already exists' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_pr_creator_needs_commit(self, workflow):
        """Test that PR creator detects uncommitted changes."""
        with patch.object(workflow, 'run_command') as mock_run:
            mock_run.side_effect = [
                {'output': 'feature-branch\n', 'exit_code': 0},
                {'output': 'M file.js\n', 'exit_code': 0},
            ]
            with patch.object(workflow, 'notify'):
                state = {'retry_count': 0}
                result = await workflow.pr_creator(state)

                assert result['review_status'] == 'needs_commit'

    @pytest.mark.asyncio
    async def test_pr_creator_skips_on_main_branch(self, workflow):
        """Test that PR creator skips on main branch."""
        with patch.object(workflow, 'run_command') as mock_run:
            mock_run.return_value = {'output': 'main\n', 'exit_code': 0}

            state = {'retry_count': 0}
            result = await workflow.pr_creator(state)

            assert result['review_status'] == 'pr_skipped'


class TestConditionalLogic:
    """Tests for conditional state transitions."""

    def test_should_continue_from_test_on_pass(self, workflow):
        """Test transition from test to reviewer on pass."""
        assert workflow.should_continue_from_test({'test_output': 'PASS'}) == 'reviewer'

    def test_should_continue_from_test_on_fail(self, workflow):
        """Test transition from test to coder on fail."""
        assert workflow.should_continue_from_test({'test_output': 'FAIL', 'retry_count': 0}) == 'coder'

    def test_should_continue_from_test_max_retries(self, workflow):
        """Test END transition on max retries."""
        from langgraph.graph import END
        assert workflow.should_continue_from_test({'test_output': 'FAIL', 'retry_count': 4}) == END

    def test_should_continue_from_review_on_approved(self, workflow):
        """Test transition from review to pr_creator on approval."""
        assert workflow.should_continue_from_review({'review_status': 'approved'}) == 'pr_creator'

    def test_should_continue_from_review_on_rejected(self, workflow):
        """Test transition from review to coder on rejection."""
        assert workflow.should_continue_from_review({'review_status': 'rejected', 'retry_count': 0}) == 'coder'

    def test_should_continue_from_pr_creator_on_success(self, workflow):
        """Test END transition on PR creation success."""
        from langgraph.graph import END
        assert workflow.should_continue_from_pr_creator({'review_status': 'pr_created'}) == END

    def test_should_continue_from_pr_creator_on_needs_commit(self, workflow):
        """Test transition to coder on needs_commit."""
        assert workflow.should_continue_from_pr_creator({'review_status': 'needs_commit', 'retry_count': 0}) == 'coder'


class TestHelpers:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_run_command_strips_null_bytes(self, workflow):
        """Test that run_command strips null bytes."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'file1\x00.txt\n', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await workflow.run_command('ls')

            assert '\x00' not in result['output']
            assert result['output'] == 'file1.txt\n'

    @pytest.mark.asyncio
    async def test_run_command_strips_ansi(self, workflow):
        """Test that run_command strips ANSI codes."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'\x1B[31mRed Text\x1B[0m', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await workflow.run_command('ls')

            assert result['output'] == 'Red Text'

    @pytest.mark.asyncio
    async def test_get_tmux_session(self, workflow):
        """Test getting tmux session name."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b'my-session\n', b''))
            mock_exec.return_value = mock_proc

            session = await workflow.get_tmux_session()
            assert session == 'my-session'

    @pytest.mark.asyncio
    async def test_get_tmux_session_no_tmux(self, workflow):
        """Test fallback when tmux is not available."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_exec.side_effect = Exception('tmux not found')

            session = await workflow.get_tmux_session()
            assert session == 'no-tmux'


class TestInvokeGemini:
    """Tests for Gemini CLI invocation with fallback."""

    @pytest.mark.asyncio
    async def test_invoke_gemini_success_first_model(self, workflow):
        """Test successful invocation with first model."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'Response from first model', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await workflow.invoke_gemini('Hello')

            assert result == 'Response from first model'
            assert mock_exec.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_gemini_quota_fallback(self, workflow):
        """Test fallback to next model on quota error."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            # First call fails with quota error
            mock_proc1 = AsyncMock()
            mock_proc1.stdout.read = AsyncMock(return_value=b'')
            mock_proc1.stderr.read = AsyncMock(side_effect=[b'TerminalQuotaError', b''])
            mock_proc1.wait = AsyncMock(return_value=1)

            # Second call succeeds
            mock_proc2 = AsyncMock()
            mock_proc2.stdout.read = AsyncMock(side_effect=[b'Response from second model', b''])
            mock_proc2.stderr.read = AsyncMock(return_value=b'')
            mock_proc2.wait = AsyncMock(return_value=0)

            mock_exec.side_effect = [mock_proc1, mock_proc2]

            result = await workflow.invoke_gemini('Hello')

            assert result == 'Response from second model'
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_gemini_non_quota_error_immediate_fail(self, workflow):
        """Test immediate failure on non-quota errors."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(return_value=b'')
            mock_proc.stderr.read = AsyncMock(side_effect=[b'Some other error', b''])
            mock_proc.wait = AsyncMock(return_value=1)
            mock_exec.return_value = mock_proc

            with pytest.raises(Exception, match='Gemini CLI exited with code 1'):
                await workflow.invoke_gemini('Hello')

            assert mock_exec.call_count == 1


class TestNotifications:
    """Tests for notification system."""

    @pytest.mark.asyncio
    async def test_notify_does_nothing_without_channel(self, workflow):
        """Test that notify does nothing when NTFY_CHANNEL is not set."""
        os.environ.pop('NTFY_CHANNEL', None)

        with patch.object(workflow, 'run_command') as mock_run:
            await workflow.notify('Title', 'Message')
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_calls_curl_with_channel(self, workflow):
        """Test that notify calls curl when NTFY_CHANNEL is set."""
        os.environ['NTFY_CHANNEL'] = 'test-channel'

        with patch.object(workflow, 'get_tmux_session', return_value='test-session'):
            with patch.object(workflow, 'run_command') as mock_run:
                await workflow.notify('Title', 'Message', 4)

                mock_run.assert_called_once()
                args = mock_run.call_args[0][1]
                assert 'Title: Title' in args
                assert 'Priority: 4' in args
                assert 'test-channel' in args[-1]


class TestVerboseLogging:
    """Tests for verbose logging."""

    @pytest.mark.asyncio
    async def test_coder_logs_prompt_when_verbose(self, capsys):
        """Test that coder logs system prompt when verbose is True."""
        workflow = WorkflowManager(verbose=True)

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'Response', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'messages': [HumanMessage(content='Test prompt')]}
            await workflow.coder(state)

            captured = capsys.readouterr()
            assert '[VERBOSE] Coder System Prompt' in captured.out

    @pytest.mark.asyncio
    async def test_reviewer_logs_prompt_when_verbose(self, capsys):
        """Test that reviewer logs system prompt when verbose is True."""
        workflow = WorkflowManager(verbose=True)

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'APPROVED', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            state = {'test_output': 'PASS', 'retry_count': 0}
            await workflow.reviewer(state)

            captured = capsys.readouterr()
            assert '[VERBOSE] Reviewer System Prompt' in captured.out
