import os
import sys

import pytest

from copium_loop.shell import stream_subprocess


@pytest.mark.asyncio
async def test_stream_subprocess_segregation():
    """
    Verify that stream_subprocess segregates stdout and stderr.
    This test is expected to fail initially because stream_subprocess
    currently returns a 4-tuple and merges stdout/stderr.
    """
    # Simple python script that writes to both stdout and stderr
    script = "import sys; sys.stdout.write('out\\n'); sys.stderr.write('err\\n')"
    command = sys.executable
    args = ["-c", script]
    env = os.environ.copy()

    # After refactor, this should return a 5-tuple:
    # (stdout, stderr, exit_code, timed_out, timeout_message)
    # But currently it returns a 4-tuple:
    # (full_output, exit_code, timed_out, timeout_message)

    result = await stream_subprocess(
        command, args, env, node=None, command_timeout=10, capture_stderr=True
    )

    # This assertion will fail because currently len(result) is 4
    assert len(result) == 5
    stdout, stderr, exit_code, timed_out, timeout_message = result

    assert stdout.strip() == "out"
    assert stderr.strip() == "err"
    assert exit_code == 0
    assert not timed_out
