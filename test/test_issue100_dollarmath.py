from mdit_py_plugins.dollarmath.index import is_escaped


class MockState:
    def __init__(self, src):
        self.src = src


def test_is_escaped_at_start():
    state = MockState("$")
    # if $ is at index 0, back_pos is 0
    # it should not be escaped and should not access index -1
    assert not is_escaped(state, 0)


def test_is_escaped_with_backslash():
    state = MockState("\\$")
    assert is_escaped(state, 1)


def test_is_escaped_with_double_backslash():
    state = MockState("\\\\$")
    assert not is_escaped(state, 2)


def test_is_escaped_wrap_around_bug():
    # If the string ends with a backslash, but we check the first character
    state = MockState("$\\")
    # back_pos is 0 (the $). It should NOT be escaped.
    # The buggy implementation will check src[-1] which is \ and say it IS escaped.
    assert not is_escaped(state, 0)
