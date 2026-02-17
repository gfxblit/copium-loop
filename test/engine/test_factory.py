import pytest

from copium_loop.engine.factory import get_engine
from copium_loop.engine.gemini import GeminiEngine
from copium_loop.engine.jules import JulesEngine


def test_get_engine_gemini():
    engine = get_engine("gemini")
    assert isinstance(engine, GeminiEngine)

def test_get_engine_jules():
    engine = get_engine("jules")
    assert isinstance(engine, JulesEngine)

def test_get_engine_default():
    engine = get_engine()
    assert isinstance(engine, GeminiEngine)

def test_get_engine_invalid():
    with pytest.raises(ValueError, match="Unknown engine: unknown"):
        get_engine("unknown")
