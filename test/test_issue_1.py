
import pytest
from unittest.mock import patch, AsyncMock
from copium_loop.nodes import tester
import os

@pytest.mark.asyncio
class TestTesterDetection:
    async def test_detects_npm(self):
        """Test that npm test is used when package.json exists."""
        with patch('os.path.exists') as mock_exists:
            # Simulate only package.json existing
            mock_exists.side_effect = lambda p: p == 'package.json'
            
            with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = {'output': 'PASS', 'exit_code': 0}
                
                await tester({'retry_count': 0})
                
                # Check that run_command was called with npm test
                mock_run.assert_called_with('npm', ['test'])

    async def test_detects_pytest(self):
        """Test that pytest is used when pyproject.toml exists."""
        with patch('os.path.exists') as mock_exists:
            # Simulate only pyproject.toml existing
            mock_exists.side_effect = lambda p: p == 'pyproject.toml'
            
            with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = {'output': 'PASS', 'exit_code': 0}
                
                await tester({'retry_count': 0})
                
                # Check that run_command was called with pytest
                mock_run.assert_called_with('pytest', [])

    async def test_env_var_override(self):
        """Test that COPIUM_TEST_CMD overrides detection."""
        with patch.dict(os.environ, {'COPIUM_TEST_CMD': 'custom test --flag'}):
            with patch('copium_loop.nodes.run_command', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = {'output': 'PASS', 'exit_code': 0}
                
                await tester({'retry_count': 0})
                
                # Check that run_command was called with custom command
                mock_run.assert_called_with('custom', ['test', '--flag'])
