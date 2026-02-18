from abc import ABC, abstractmethod


class SyncStrategy(ABC):
    """Abstract base class for synchronization strategies."""

    @abstractmethod
    async def execute(self, node: str, timeout: int) -> None:
        """Executes the synchronization strategy."""
        pass


class FullPullStrategy(SyncStrategy):
    """Performs a full git pull."""

    async def execute(self, node: str, timeout: int) -> None:  # noqa: ARG002
        from copium_loop.git import pull

        res = await pull(node=node)
        if res["exit_code"] != 0:
            from copium_loop.engine.base import LLMError

            raise LLMError(f"Failed to pull changes: {res['output']}")


class SelectiveFileStrategy(SyncStrategy):
    """Performs a fetch and selective checkout of specific files."""

    def __init__(self, filenames: list[str]):
        self.filenames = filenames

    async def execute(self, node: str, timeout: int) -> None:
        import os

        from copium_loop.shell import stream_subprocess

        # git fetch
        await stream_subprocess("git", ["fetch"], os.environ, node, timeout)
        # git checkout FETCH_HEAD -- filenames
        if self.filenames:
            cmd = ["checkout", "FETCH_HEAD", "--"] + self.filenames
            await stream_subprocess("git", cmd, os.environ, node, timeout)
            # It's okay if files don't exist (node might not have written them)


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
        sync_strategy: SyncStrategy | None = None,
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
