from copium_loop.engine.base import LLMEngine
from copium_loop.engine.gemini import GeminiEngine
from copium_loop.engine.jules import JulesEngine


def get_engine(name: str | None = None) -> LLMEngine:
    """
    Returns an LLMEngine instance based on the provided name.
    If name is None, returns the default GeminiEngine.
    """
    if name is None or name == "gemini":
        return GeminiEngine()
    if name == "jules":
        return JulesEngine()
    raise ValueError(f"Unknown engine: {name}")
