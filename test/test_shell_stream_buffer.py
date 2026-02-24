import os
import sys

import pytest

from copium_loop.shell import StreamBuffer, stream_subprocess


def test_stream_buffer_truncation():
    limit = 10
    buffer = StreamBuffer(limit, "Test")
    buffer.append("12345")
    assert buffer.get_content() == "12345"
    assert not buffer.truncated

    buffer.append("67890")
    # Exactly limit, should NOT be truncated yet.
    assert buffer.get_content() == "1234567890"

    buffer.append("!")
    assert buffer.truncated
    assert buffer.get_content() == "1234567890\n[... Test Truncated ...]\n"

    buffer.append("more")
    # Should not add more
    assert buffer.get_content() == "1234567890\n[... Test Truncated ...]\n"


@pytest.mark.asyncio
async def test_stream_subprocess_interleaving():
    # A script that writes to stdout then stderr then stdout
    script = "import sys; import time; sys.stdout.write('out1\\n'); sys.stdout.flush(); time.sleep(0.05); sys.stderr.write('err1\\n'); sys.stderr.flush(); time.sleep(0.05); sys.stdout.write('out2\\n'); sys.stdout.flush()"
    command = sys.executable
    args = ["-c", script]
    env = os.environ.copy()

    # Expecting 6-tuple: (stdout, stderr, interleaved, exit_code, timed_out, timeout_message)
    result = await stream_subprocess(
        command, args, env, node=None, command_timeout=10, capture_stderr=True
    )

    assert len(result) == 6
    stdout, stderr, interleaved, exit_code, timed_out, timeout_message = result

    assert "out1" in stdout
    assert "out2" in stdout
    assert "err1" not in stdout

    assert "err1" in stderr
    assert "out1" not in stderr

    # Interleaved should have both in order
    assert "out1" in interleaved
    assert "err1" in interleaved
    assert "out2" in interleaved

    out1_idx = interleaved.find("out1")
    err1_idx = interleaved.find("err1")
    out2_idx = interleaved.find("out2")

    assert out1_idx < err1_idx < out2_idx
