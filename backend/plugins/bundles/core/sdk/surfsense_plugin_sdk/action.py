"""An action: a function the app can run, under the name manifest.json declares for it.

@action marks one; the run command finds it here by that name.
"""

from collections.abc import Callable

type ActionFunction = Callable[..., object]

_actions: dict[str, ActionFunction] = {}


def action[F: ActionFunction](name: str) -> Callable[[F], F]:
    """Marks the function the app runs for the action manifest.json names."""

    def register(function: F) -> F:
        """Hands the function back unchanged, so the plugin can still call it."""
        marked = _actions.get(name)
        if marked is not None:
            raise ValueError(
                f'@action("{name}") is on two functions:'
                f" {marked.__qualname__} and {function.__qualname__}"
            )
        _actions[name] = function
        return function

    return register


def registered_action(name: str) -> ActionFunction | None:
    """The function marked for this action, or None when main.py marked none."""
    return _actions.get(name)
