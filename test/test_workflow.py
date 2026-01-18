"Tests for copium_loop workflow."

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from copium_loop.copium_loop import WorkflowManager
from copium_loop.state import AgentState
from copium_loop.nodes import coder, tester, reviewer, pr_creator, should_continue_from_test, should_continue_from_review, should_continue_from_pr_creator
from copium_loop import utils
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END


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

    @pytest.mark.parametrize("start_node", ["coder", "tester", "reviewer", "pr_creator"])
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
    async def test_coder_returns_coded_status(self):
        """Test that coder node returns coded status."""
        with patch('copium_loop.nodes.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Mocked Code Response'

            state = {'messages': [HumanMessage(content='Build a login form')]}
            result = await coder(state)

            assert result['code_status'] == 'coded'
            assert 'Mocked Code Response' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_coder_includes_test_failure_in_prompt(self):
        """Test that coder includes test failure in prompt."""
        with patch('copium_loop.nodes.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Fixing...'

            state = {
                'messages': [HumanMessage(content='Fix bug')],
                'test_output': 'FAIL: Expected 1 to be 2'
            }
            await coder(state)

            # Check that the prompt contains the test failure
            call_args = mock_gemini.call_args[0]
            prompt = call_args[0]
            assert 'Your previous implementation failed tests.' in prompt
            assert 'FAIL: Expected 1 to be 2' in prompt

    @pytest.mark.asyncio
    async def test_coder_logs_prompt_when_verbose(self, capsys):
        """Test that coder logs system prompt when verbose is True."""
        with patch('copium_loop.nodes.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Response'

            state = {
                'messages': [HumanMessage(content='Test prompt')],
                'verbose': True
            }
            await coder(state)

            captured = capsys.readouterr()
            assert '[VERBOSE] Coder System Prompt' in captured.out


class TestReviewerNode:
    """Tests for the reviewer node."""

    @pytest.mark.asyncio
    async def test_reviewer_returns_approved(self):
        """Test that reviewer returns approved status."""
        with patch('copium_loop.nodes.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'APPROVED'

            state = {'test_output': 'PASS', 'retry_count': 0}
            result = await reviewer(state)

            assert result['review_status'] == 'approved'

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self):
        """Test that reviewer returns rejected status."""
        with patch('copium_loop.nodes.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'REJECTED: issues'

            state = {'test_output': 'PASS', 'retry_count': 0}
            result = await reviewer(state)

            assert result['review_status'] == 'rejected'
            assert result['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_reviewer_rejects_on_test_failure(self):
        """Test that reviewer rejects when tests fail."""
        state = {'test_output': 'FAIL', 'retry_count': 0}
        result = await reviewer(state)

        assert result['review_status'] == 'rejected'
        assert result['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_reviewer_allows_empty_test_output(self):
        """Test that reviewer proceeds with empty test output."""
        with patch('copium_loop.nodes.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Thinking...\nAPPROVED'

            state = {'test_output': '', 'retry_count': 0}
            result = await reviewer(state)

            assert result['review_status'] == 'approved'


class TestTesterNode:
    """Tests for the test runner node."""

    @pytest.mark.asyncio
    async def test_tester_returns_pass(self):
        """Test that test runner returns PASS on success."""
        with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {'output': 'All tests passed', 'exit_code': 0}

            state = {'retry_count': 0}
            result = await tester(state)

            assert result['test_output'] == 'PASS'

    @pytest.mark.asyncio
    async def test_tester_returns_fail(self):
        """Test that test runner returns FAIL on failure."""
        with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {'output': 'FAIL tests', 'exit_code': 1}
            with patch('copium_loop.nodes.notify', new_callable=AsyncMock) as mock_notify:
                state = {'retry_count': 0}
                result = await tester(state)

                assert 'FAIL' in result['test_output']
                assert result['retry_count'] == 1


class TestPrCreatorNode:
    """Tests for the PR creator node."""

    @pytest.mark.asyncio
    async def test_pr_creator_creates_pr(self):
        """Test that PR creator creates a PR successfully."""
        with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                {'output': 'feature-branch\n', 'exit_code': 0},  # branch
                {'output': '', 'exit_code': 0},  # status
                {'output': '', 'exit_code': 0},  # push
                {'output': 'https://github.com/org/repo/pull/1\n', 'exit_code': 0},  # pr
            ]

            state = {'retry_count': 0}
            result = await pr_creator(state)

            assert result['review_status'] == 'pr_created'
            assert 'PR Created' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_pr_creator_handles_existing_pr(self):
        """Test that PR creator handles existing PR."""
        with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                {'output': 'feature-branch\n', 'exit_code': 0},
                {'output': '', 'exit_code': 0},
                {'output': '', 'exit_code': 0},
                {'output': 'already exists: https://github.com/org/repo/pull/1\n', 'exit_code': 1},
            ]

            state = {'retry_count': 0}
            result = await pr_creator(state)

            assert result['review_status'] == 'pr_created'
            assert 'already exists' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_pr_creator_needs_commit(self):
        """Test that PR creator detects uncommitted changes."""
        with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                {'output': 'feature-branch\n', 'exit_code': 0},
                {'output': 'M file.js\n', 'exit_code': 0},
            ]
            with patch('copium_loop.nodes.notify', new_callable=AsyncMock):
                state = {'retry_count': 0}
                result = await pr_creator(state)

                assert result['review_status'] == 'needs_commit'

    @pytest.mark.asyncio
    async def test_pr_creator_skips_on_main_branch(self):
        """Test that PR creator skips on main branch."""
        with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {'output': 'main\n', 'exit_code': 0}

            state = {'retry_count': 0}
            result = await pr_creator(state)

            assert result['review_status'] == 'pr_skipped'


class TestConditionalLogic:
    """Tests for conditional state transitions."""

    def test_should_continue_from_test_on_pass(self):
        """Test transition from test to reviewer on pass."""
        assert should_continue_from_test({'test_output': 'PASS'}) == 'reviewer'

    def test_should_continue_from_test_on_fail(self):
        """Test transition from test to coder on fail."""
        assert should_continue_from_test({'test_output': 'FAIL', 'retry_count': 0}) == 'coder'

    def test_should_continue_from_test_max_retries(self):
        """Test END transition on max retries."""
        assert should_continue_from_test({'test_output': 'FAIL', 'retry_count': 4}) == END

    def test_should_continue_from_review_on_approved(self):
        """Test transition from review to pr_creator on approval."""
        assert should_continue_from_review({'review_status': 'approved'}) == 'pr_creator'

    def test_should_continue_from_review_on_rejected(self):
        """Test transition from review to coder on rejection."""
        assert should_continue_from_review({'review_status': 'rejected', 'retry_count': 0}) == 'coder'

    def test_should_continue_from_pr_creator_on_success(self):
        """Test END transition on PR creation success."""
        assert should_continue_from_pr_creator({'review_status': 'pr_created'}) == END

    def test_should_continue_from_pr_creator_on_needs_commit(self):
        """Test transition to coder on needs_commit."""
        assert should_continue_from_pr_creator({'review_status': 'needs_commit', 'retry_count': 0}) == 'coder'


class TestHelpers:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_run_command_strips_null_bytes(self):
        """Test that run_command strips null bytes."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'file1\x00.txt\n', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await utils.run_command('ls')

            assert '\x00' not in result['output']
            assert result['output'] == 'file1.txt\n'

    @pytest.mark.asyncio
    async def test_run_command_strips_ansi(self):
        """Test that run_command strips ANSI codes."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b'\x1B[31mRed Text\x1B[0m', b''])
            mock_proc.stderr.read = AsyncMock(return_value=b'')
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await utils.run_command('ls')

            assert result['output'] == 'Red Text'

    @pytest.mark.asyncio
    async def test_get_tmux_session(self):
        """Test getting tmux session name."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b'my-session\n', b''))
            mock_exec.return_value = mock_proc

            session = await utils.get_tmux_session()
            assert session == 'my-session'

    @pytest.mark.asyncio
    async def test_get_tmux_session_no_tmux(self):
        """Test fallback when tmux is not available."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_exec.side_effect = Exception('tmux not found')

            session = await utils.get_tmux_session()
            assert session == 'no-tmux'


class TestInvokeGemini:
    """Tests for Gemini CLI invocation with fallback."""

    @pytest.mark.asyncio
    async def test_invoke_gemini_success_first_model(self):
        """Test successful invocation with first model."""
        with patch('copium_loop.utils._execute_gemini', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = 'Response from first model'
            
            result = await utils.invoke_gemini('Hello')

            assert result == 'Response from first model'
            assert mock_exec.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_gemini_quota_fallback(self):
        """Test fallback to next model on quota error."""
        with patch('copium_loop.utils._execute_gemini', new_callable=AsyncMock) as mock_exec:
            # Setup side effects to simulate failure then success
            mock_exec.side_effect = [
                Exception('TerminalQuotaError'),
                'Response from second model'
            ]

            result = await utils.invoke_gemini('Hello')

            assert result == 'Response from second model'
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_gemini_non_quota_error_immediate_fail(self):
        """Test immediate failure on non-quota errors."""
        with patch('copium_loop.utils._execute_gemini', new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception('Gemini CLI exited with code 1')

            with pytest.raises(Exception, match='Gemini CLI exited with code 1'):
                await utils.invoke_gemini('Hello')

            assert mock_exec.call_count == 1


class TestNotifications:
    """Tests for notification system."""

    @pytest.mark.asyncio
    async def test_notify_does_nothing_without_channel(self):
        """Test that notify does nothing when NTFY_CHANNEL is not set."""
        os.environ.pop('NTFY_CHANNEL', None)

        with patch('copium_loop.utils.run_command', new_callable=AsyncMock) as mock_run:
            await utils.notify('Title', 'Message')
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_calls_curl_with_channel(self):
        """Test that notify calls curl when NTFY_CHANNEL is set."""
        os.environ['NTFY_CHANNEL'] = 'test-channel'

        with patch('copium_loop.utils.get_tmux_session', return_value='test-session'):
            with patch('copium_loop.utils.run_command', new_callable=AsyncMock) as mock_run:
                await utils.notify('Title', 'Message', 4)

                mock_run.assert_called_once()
                args = mock_run.call_args[0][1]
                assert 'Title: Title' in args
                assert 'Priority: 4' in args
                assert 'test-channel' in args[-1]