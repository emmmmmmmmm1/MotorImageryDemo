from __future__ import annotations

from typing import Any, Callable, Type

from .base import BaseDecoder

_REGISTRY: dict[str, Type[BaseDecoder]] = {}


def register(name: str) -> Callable[[Type[BaseDecoder]], Type[BaseDecoder]]:
    def deco(cls: Type[BaseDecoder]) -> Type[BaseDecoder]:
        if not issubclass(cls, BaseDecoder):
            raise TypeError(f"{cls.__name__} must subclass BaseDecoder")
        if name in _REGISTRY and _REGISTRY[name] is not cls:
            raise ValueError(f"decoder name {name!r} already registered")
        _REGISTRY[name] = cls
        return cls

    return deco


def build(name: str, **kwargs: Any) -> BaseDecoder:
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown decoder {name!r}. available: {list_available()}"
        )
    return _REGISTRY[name](**kwargs)


def list_available() -> list[str]:
    return sorted(_REGISTRY.keys())
