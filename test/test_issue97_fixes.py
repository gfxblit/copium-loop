import pytest
from unittest.mock import patch, MagicMock
import io
from langgraph.graph import END
from copium_loop import constants
from copium_loop.nodes.conditionals import should_continue_from_coder

def test_should_continue_from_coder_log_injection():
    """Verify that should_continue_from_coder sanitizes code_status in logs."""
    state = {"code_status": "failed\nINJECTION", "retry_count": 0}
    
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        result = should_continue_from_coder(state)
        output = fake_out.getvalue()
        
    assert result == "coder"
    # If it uses repr(), it should have 'failed\\nINJECTION' or similar
    assert "failed\nINJECTION" not in output
    assert "failed\\nINJECTION" in output

def test_should_continue_from_coder_off_by_one():
    """Verify that should_continue_from_coder stops at exactly MAX_RETRIES."""
    # If MAX_RETRIES is 10, we expect it to stop when retry_count reaches 10.
    state = {"code_status": "failed", "retry_count": constants.MAX_RETRIES}
    
    result = should_continue_from_coder(state)
    
    # Current implementation returns "coder" for retry_count == MAX_RETRIES
    # We want it to return END to align with MAX_RETRIES total failures/attempts.
    assert result == END