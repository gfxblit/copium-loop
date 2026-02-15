import pytest

from copium_loop.engine.factory import engine_factory
from copium_loop.engine.gemini import GeminiEngine
from copium_loop.engine.jules import JulesEngine


def test_engine_factory_gemini():
    engine = engine_factory("gemini")
    assert isinstance(engine, GeminiEngine)

def test_engine_factory_jules():
    engine = engine_factory("jules")
    assert isinstance(engine, JulesEngine)

def test_engine_factory_default():
    # Should default to gemini if None or empty
    assert isinstance(engine_factory(None), GeminiEngine)
    assert isinstance(engine_factory(""), GeminiEngine)

def test_engine_factory_invalid():
    with pytest.raises(ValueError, match="Unknown engine: unknown"):
        engine_factory("unknown")
