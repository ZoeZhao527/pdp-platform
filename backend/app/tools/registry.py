from datetime import datetime
from typing import Any, Callable


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, func: Callable[..., Any]) -> None:
        self._tools[name] = func

    def call(self, name: str, **kwargs: Any) -> Any:
        func = self._tools.get(name)
        if func is None:
            raise KeyError(f"工具未注册: {name}")
        return func(**kwargs)

    def names(self) -> list[str]:
        return sorted(self._tools)


def _current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _echo(**kwargs: Any) -> dict[str, Any]:
    return {"echo": kwargs}


tool_registry = ToolRegistry()
tool_registry.register("current_time", _current_time)
tool_registry.register("echo", _echo)

