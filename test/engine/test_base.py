import pytest

from copium_loop.engine.base import LLMEngine


def test_llm_engine_interface():
    """Verify that LLMEngine cannot be instantiated and defines required methods."""
    with pytest.raises(TypeError):
        LLMEngine()

    class MockEngine(LLMEngine):
        @property
        def engine_type(self):
            return "mock"

        async def invoke(
            self,
            _prompt,
            args=None,  # noqa: ARG002
            models=None,  # noqa: ARG002
            verbose=False,  # noqa: ARG002
            label=None,  # noqa: ARG002
            node=None,  # noqa: ARG002
            command_timeout=None,  # noqa: ARG002
            inactivity_timeout=None,  # noqa: ARG002
            sync_strategy=None,  # noqa: ARG002
        ):
            return "mocked"

        def sanitize_for_prompt(self, text, _max_length=12000):
            return text

        def get_required_tools(self):
            return []

    engine = MockEngine()
    assert engine is not None
    assert engine.engine_type == "mock"
