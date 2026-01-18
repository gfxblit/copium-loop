import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage
from copium_loop.nodes import coder

class TestCoderNode:
    """Tests for the coder node."""

    @pytest.mark.asyncio
    async def test_coder_returns_coded_status(self):
        """Test that coder node returns coded status."""
        with patch('copium_loop.nodes.coder.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Mocked Code Response'

            state = {'messages': [HumanMessage(content='Build a login form')]}
            result = await coder(state)

            assert result['code_status'] == 'coded'
            assert 'Mocked Code Response' in result['messages'][0].content

    @pytest.mark.asyncio
    async def test_coder_includes_test_failure_in_prompt(self):
        """Test that coder includes test failure in prompt."""
        with patch('copium_loop.nodes.coder.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
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
        with patch('copium_loop.nodes.coder.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Response'

            state = {
                'messages': [HumanMessage(content='Test prompt')],
                'verbose': True
            }
            await coder(state)

            captured = capsys.readouterr()
            assert '[VERBOSE] Coder System Prompt' in captured.out
