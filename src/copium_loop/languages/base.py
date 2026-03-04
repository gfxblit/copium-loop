from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Command:
    executable: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None

    def __str__(self) -> str:
        args_str = " ".join(self.args)
        res = f"{self.executable} {args_str}".strip()
        if self.cwd:
            return f"(cd {self.cwd} && {res})"
        return res


@dataclass
class CompositeCommand:
    commands: list[Command] = field(default_factory=list)

    def __str__(self) -> str:
        return " && ".join(str(cmd) for cmd in self.commands)


class LanguageStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def match(self, path: str) -> bool:
        pass

    @abstractmethod
    def get_test_command(self, path: str) -> Command | CompositeCommand | None:
        pass

    @abstractmethod
    def get_build_command(self, path: str) -> Command | CompositeCommand | None:
        pass

    @abstractmethod
    def get_lint_command(self, path: str) -> Command | CompositeCommand | None:
        pass
