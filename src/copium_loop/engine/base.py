from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for LLM engines."""


class LLMEngine(ABC):
    """Abstract base class for LLM engines."""

    @property
    @abstractmethod
    def engine_type(self) -> str:
        """Returns the type of the engine (e.g., 'gemini', 'jules')."""
        pass

    @abstractmethod
    async def invoke(
        self,
        prompt: str,
        args: list[str] | None = None,
        models: list[str | None] | None = None,
        verbose: bool = False,
        label: str | None = None,
        node: str | None = None,
        command_timeout: int | None = None,
        inactivity_timeout: int | None = None,
        jules_metadata: dict[str, str] | None = None,
    ) -> str:
        """Invokes the LLM with a prompt."""
        pass

    @abstractmethod
    def sanitize_for_prompt(self, text: str, max_length: int = 12000) -> str:
        """Sanitizes text for inclusion in a prompt."""
        pass

    @abstractmethod
    def get_required_tools(self) -> list[str]:
        """Returns a list of required CLI tools for the engine."""
        pass
