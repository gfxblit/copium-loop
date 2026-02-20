import re
import threading

import mdit_py_plugins.dollarmath.index as dollarmath
import pytest
from linkify_it import LinkifyIt
from linkify_it.ucre import _re_src_path


class MockState:
    def __init__(self, src):
        self.src = src


def test_is_escaped_at_start():
    state = MockState("$")
    # if $ is at index 0, back_pos is 0
    # it should not be escaped and should not access index -1
    assert not dollarmath.is_escaped(state, 0)


def test_is_escaped_with_backslash():
    state = MockState("\\$")
    assert dollarmath.is_escaped(state, 1)


def test_is_escaped_with_double_backslash():
    state = MockState("\\\\$")
    assert not dollarmath.is_escaped(state, 2)


def test_is_escaped_wrap_around_bug():
    # If the string ends with a backslash, but we check the first character
    state = MockState("$\\")
    # back_pos is 0 (the $). It should NOT be escaped.
    # The buggy implementation will check src[-1] which is \ and say it IS escaped.
    assert not dollarmath.is_escaped(state, 0)


def test_re_src_path_compilation():
    opts = {}
    path_regex = _re_src_path(opts)
    # This should not raise re.error
    try:
        re.compile(path_regex)
    except re.error as e:
        pytest.fail(f"Regex compilation failed: {e}")


def test_linkify_race_condition():
    def validate_a(_self, _text, _pos):
        return 0

    def validate_b(_self, _text, _pos):
        return 0

    errors = []

    def worker(name, validator):
        schemas = {"test:": {"validate": validator}}

        linker = LinkifyIt(schemas)

        # Check if the validator is correctly bound
        # logic in main.py: compiled["validate"] = types.MethodType(val.get("validate"), self)

        # Access internal structure to verify
        if "test:" not in linker._compiled:
            errors.append(
                f"FAIL: Schema 'test:' not found in compiled schemas for thread {name}"
            )
            return

        bound_method = linker._compiled["test:"]["validate"]

        if hasattr(LinkifyIt, "func"):
            errors.append(
                f"FAIL: LinkifyIt class polluted with 'func' attribute in thread {name}"
            )
            return

        # Check if the bound method corresponds to the correct function
        if bound_method.__func__ is not validator:
            errors.append(
                f"FAIL: Validator mismatch in thread {name}. Expected {validator}, got {bound_method.__func__}"
            )

    t1 = threading.Thread(target=worker, args=("A", validate_a))
    t2 = threading.Thread(target=worker, args=("B", validate_b))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    if hasattr(LinkifyIt, "func"):
        errors.append(
            "FAIL: LinkifyIt class still has 'func' attribute after threads finished."
        )

    assert not errors, "\n".join(errors)
