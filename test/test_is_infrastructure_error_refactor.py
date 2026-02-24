from copium_loop.errors import is_infrastructure_error


def test_is_infrastructure_error_location():
    assert is_infrastructure_error("Could not resolve host: github.com") is True
    assert is_infrastructure_error("Not an error") is False
