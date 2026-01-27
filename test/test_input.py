from unittest.mock import MagicMock, patch

from copium_loop.ui import InputReader


def test_input_reader_single_char():
    """Test reading a single character."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch('copium_loop.ui.os.read', return_value=b'q'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == 'q'

def test_input_reader_tab():
    """Test reading a Tab key."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch('copium_loop.ui.os.read', return_value=b'\t'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == '\t'

def test_input_reader_arrow_right():
    """Test reading a Right Arrow key escape sequence."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch('copium_loop.ui.os.read', return_value=b'\x1b[C'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == '\x1b[C'

def test_input_reader_arrow_left():
    """Test reading a Left Arrow key escape sequence."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch('copium_loop.ui.os.read', return_value=b'\x1b[D'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == '\x1b[D'

def test_input_reader_shift_tab():
    """Test reading a Shift+Tab escape sequence."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    with (
        patch('copium_loop.ui.os.read', return_value=b'\x1b[Z'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == '\x1b[Z'

def test_input_reader_buffered_keys():
    """Test that multiple keys read at once are buffered and returned one by one."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0
    # Read two keys at once
    with (
        patch('copium_loop.ui.os.read', return_value=b'q1'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == 'q'

    # Second call should return '1' without calling select/os.read
    with patch('copium_loop.ui.select.select') as mock_select:
        assert reader.get_key() == '1'
        mock_select.assert_not_called()

def test_input_reader_partial_sequence_buffering():
    """Test that partial escape sequences are buffered until complete."""
    reader = InputReader()
    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0

    # First part of sequence
    with (
        patch('copium_loop.ui.os.read', return_value=b'\x1b['),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() is None

    # Second part of sequence
    with (
        patch('copium_loop.ui.os.read', return_value=b'C'),
        patch('copium_loop.ui.select.select', return_value=([mock_stdin], [], [])),
        patch('copium_loop.ui.sys.stdin', mock_stdin)
    ):
        assert reader.get_key() == '\x1b[C'

def test_input_reader_timeout():
    """Test that it returns None when no input is available."""
    reader = InputReader()
    with patch('copium_loop.ui.select.select', return_value=([], [], [])):
        assert reader.get_key() is None
