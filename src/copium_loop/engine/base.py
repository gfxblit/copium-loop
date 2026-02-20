from abc import ABC, abstractmethod
from typing import Any

from copium_loop.session_manager import SessionManager


class LLMError(Exception):
    """Base exception for LLM engines."""


class LLMEngine(ABC):
    """Abstract base class for LLM engines."""

    def __init__(self):
        self.session_manager: SessionManager | None = None

    def set_session_manager(self, session_manager: SessionManager):
        """Sets the session manager for the engine."""
        self.session_manager = session_manager

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
        **kwargs: Any,
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
