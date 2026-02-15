import threading

import mdit_py_plugins.dollarmath.index as dollarmath
from linkify_it import LinkifyIt


def patch_all():
    """Apply all necessary monkey-patches to external libraries."""
    _patch_dollarmath_is_escaped()
    _patch_linkify_it_race_condition()


def _patch_dollarmath_is_escaped():
    """Fix wrap-around bug in mdit_py_plugins.dollarmath.index.is_escaped."""

    def patched_is_escaped(state, back_pos, _mod=0):
        # count how many \ are before the current position
        backslashes = 0
        while back_pos > 0:  # Fix: use > 0 instead of >= 0
            back_pos = back_pos - 1
            if state.src[back_pos] == "\\":
                backslashes += 1
            else:
                break

        if not backslashes:
            return False

        return (backslashes % 2) != 0

    dollarmath.is_escaped = patched_is_escaped


_linkify_compile_lock = threading.Lock()


def _patch_linkify_it_race_condition():
    """Fix race condition in linkify_it where it pollutes LinkifyIt class."""
    original_compile = LinkifyIt._compile

    def patched_compile(self):
        # Use a lock to ensure thread-safety when temporarily polluting the class
        with _linkify_compile_lock:
            # Save existing attribute if any
            had_func = hasattr(LinkifyIt, "func")
            old_func = getattr(LinkifyIt, "func", None)

            try:
                # This will set LinkifyIt.func
                result = original_compile(self)

                # If it was set, move it to the instance
                if hasattr(LinkifyIt, "func"):
                    # The library might have set it. We want it on the instance.
                    # Note: original_compile already used self.func which matched LinkifyIt.func
                    # but we want to make sure it's clean for other threads.
                    self.func = LinkifyIt.func
                    delattr(LinkifyIt, "func")

                return result
            finally:
                # Restore old attribute if it existed
                if had_func:
                    LinkifyIt.func = old_func
                elif hasattr(LinkifyIt, "func"):
                    # If we didn't have it before but it's there now (and we didn't move it),
                    # clear it.
                    delattr(LinkifyIt, "func")

    LinkifyIt._compile = patched_compile
