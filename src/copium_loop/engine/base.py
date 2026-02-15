from abc import ABC, abstractmethod


class LLMEngine(ABC):
    """Abstract base class for LLM engines."""

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
    ) -> str:
        """Invokes the LLM with a prompt."""
        pass

    @abstractmethod
    def sanitize_for_prompt(self, text: str, max_length: int = 12000) -> str:
        """Sanitizes text for inclusion in a prompt."""
        pass

    @abstractmethod
    async def verify(self) -> bool:
        """Verifies that the engine is correctly configured and usable."""
        pass
