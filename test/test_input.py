from unittest.mock import MagicMock, patch

from copium_loop.input_reader import InputReader


def test_input_reader_single_char():
    """Test reading a single character."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"q"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "q"


def test_input_reader_tab():
    """Test reading a Tab key."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"\t"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "\t"


def test_input_reader_arrow_right():
    """Test reading a Right Arrow key escape sequence."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"\x1b[C"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "\x1b[C"


def test_input_reader_arrow_left():
    """Test reading a Left Arrow key escape sequence."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"\x1b[D"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "\x1b[D"


def test_input_reader_shift_tab():
    """Test reading a Shift+Tab escape sequence."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"\x1b[Z"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "\x1b[Z"


def test_input_reader_buffered_keys():
    """Test that multiple keys read at once are buffered and returned one by one."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    # Read two keys at once
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"q1"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "q"

    # Second call should return '1' without calling select/os.read
    with patch("copium_loop.input_reader.select.select") as mock_select:
        assert reader.get_key() == "1"
        mock_select.assert_not_called()


def test_input_reader_partial_sequence_buffering():
    """Test that partial escape sequences are buffered until complete."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0

    # First part of sequence
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"\x1b["),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() is None

    # Second part of sequence
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"C"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "\x1b[C"


def test_input_reader_timeout():
    """Test that it returns None when no input is available."""
    reader = InputReader()
    with patch("copium_loop.input_reader.select.select", return_value=([], [], [])):
        assert reader.get_key() is None


def test_input_reader_utf8():
    """Test reading a multi-byte UTF-8 character."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    # Emoji: 👋 (UTF-8: 0xF0 0x9F 0x91 0x8B)
    with (
        patch("copium_loop.input_reader.os.read", return_value="👋".encode()),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        assert reader.get_key() == "👋"


def test_input_reader_escape_key():
    """Test reading just the Escape key (\x1b)."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", return_value=b"\x1b"),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
    ):
        # First call might return None if it thinks it might be a sequence
        # But for \x1b alone it should eventually return it
        res = reader.get_key()
        if res is None:
            # If it was waiting for more, second call with empty read or timeout should return \x1b
            with patch(
                "copium_loop.input_reader.select.select", return_value=([], [], [])
            ):
                res = reader.get_key()
        assert res == "\x1b"


def test_input_reader_oserror_handling():
    """Test that it handles OSError during read."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", side_effect=OSError("Read error")),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
        patch("sys.stderr", new_callable=MagicMock) as mock_stderr,
    ):
        assert reader.get_key() is None
        assert any(
            "Error reading from stdin" in str(arg)
            for call in mock_stderr.write.call_args_list
            for arg in call.args
        )


def test_input_reader_unexpected_exception():
    """Test that it handles unexpected exceptions during read."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch("copium_loop.input_reader.os.read", side_effect=Exception("kaboom")),
        patch(
            "copium_loop.input_reader.select.select",
            return_value=([mock_stdin], [], []),
        ),
        patch("copium_loop.input_reader.sys.stdin", mock_stdin),
        patch("sys.stderr", new_callable=MagicMock) as mock_stderr,
    ):
        assert reader.get_key() is None
        assert any(
            "Unexpected error" in str(arg)
            for call in mock_stderr.write.call_args_list
            for arg in call.args
        )
