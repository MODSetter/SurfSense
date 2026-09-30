import inspect
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Any, TypeAliasType, TypeVar, get_args, get_type_hints

import pytest

import surfsense_plugin_sdk
from surfsense_plugin_sdk.http import Response

pytestmark = pytest.mark.unit

SDK = surfsense_plugin_sdk.__name__


def _mentions_any(annotation: object) -> bool:
    """Any anywhere in a type, through aliases, bounds and generic arguments."""
    if annotation is Any:
        return True
    if isinstance(annotation, TypeAliasType):
        return _mentions_any(annotation.__value__)
    if isinstance(annotation, TypeVar):
        return _mentions_any(annotation.__bound__)
    return any(_mentions_any(argument) for argument in get_args(annotation))


def _typed_things(module: ModuleType) -> Iterator[Callable[..., object] | type]:
    """Every function, class, method and property a plugin can reach from a module."""
    names = getattr(module, "__all__", None)
    for name, thing in vars(module).items():
        listed = name in names if names else not name.startswith("_")
        if not listed:
            continue
        if isinstance(thing, ModuleType) and thing.__name__.startswith(SDK):
            yield from _typed_things(thing)
        elif getattr(thing, "__module__", "") == module.__name__ or names:
            if inspect.isclass(thing):
                yield thing
                for member_name, member in vars(thing).items():
                    if member_name.startswith("_"):
                        continue
                    if isinstance(member, property) and member.fget:
                        yield member.fget
                    elif inspect.isfunction(member):
                        yield member
            elif inspect.isfunction(thing):
                yield thing


def test_the_only_any_a_plugin_meets_is_a_sources_json() -> None:
    """Everything else is exact, so type-checking a plugin against the SDK means something."""
    typed_any = {
        thing
        for thing in _typed_things(surfsense_plugin_sdk)
        if any(_mentions_any(hint) for hint in get_type_hints(thing).values())
    }

    assert typed_any == {Response.json}
