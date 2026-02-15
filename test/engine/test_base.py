import pytest

from copium_loop.engine.base import LLMEngine


def test_llm_engine_interface():
    """Verify that LLMEngine cannot be instantiated and defines required methods."""
    with pytest.raises(TypeError):
        LLMEngine()

    class MockEngine(LLMEngine):
        async def invoke(self, _prompt, **_kwargs):
            return "mocked"

        def sanitize_for_prompt(self, text, _max_length=12000):
            return text

        async def verify(self):
            return True

    engine = MockEngine()
    assert engine is not None
