from copium_loop.engine.base import LLMEngine
from copium_loop.engine.gemini import GeminiEngine
from copium_loop.engine.jules import JulesEngine


def engine_factory(engine_type: str | None = None) -> LLMEngine:
    """
    Factory function to create an LLM engine instance.

    Args:
        engine_type: The type of engine to create ("gemini" or "jules").
                     Defaults to "gemini" if None or empty.

    Returns:
        An instance of LLMEngine.

    Raises:
        ValueError: If the engine_type is unknown.
    """
    if not engine_type:
        return GeminiEngine()

    engine_type = engine_type.lower()

    if engine_type == "gemini":
        return GeminiEngine()
    elif engine_type == "jules":
        return JulesEngine()
    else:
        raise ValueError(f"Unknown engine: {engine_type}")
