from copium_loop import constants


def test_max_retries_value():
    """Verify that MAX_RETRIES is set to 30."""
    assert constants.MAX_RETRIES == 30
