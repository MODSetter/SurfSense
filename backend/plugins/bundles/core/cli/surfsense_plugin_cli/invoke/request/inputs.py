"""The author's --input values, turned into the kinds the action declares.

Refused the way the app's run route refuses them, so a run that works here
starts in the app too.
"""

import typer
from surfsense_plugin_manifest import Action


def inputs_for(action: Action, typed: list[str]) -> dict[str, object]:
    """Every value converted, or every problem named at once."""
    declared = {each.name: each for each in action.inputs}
    values: dict[str, object] = {}
    errors: list[str] = []
    for entry in typed:
        name, separator, text = entry.partition("=")
        if not separator:
            errors.append(f"{entry}: an input is name=value")
        elif name not in declared:
            errors.append(f'{action.name} has no input named "{name}"')
        else:
            try:
                values[name] = _as_kind(declared[name].kind, text)
            except ValueError as wrong:
                errors.append(f"{name} must be {wrong}, not {text}")
    errors += [
        f"{each.name} is required: pass --input {each.name}=…"
        for each in action.inputs
        if each.required and each.name not in values and each.name not in _typed(typed)
    ]
    if errors:
        for error in errors:
            typer.echo(error, err=True)
        raise typer.Exit(1)
    return values


def _as_kind(kind: str, text: str) -> object:
    """The value a declared kind means; a ValueError says what it had to be."""
    if kind == "number":
        for number in (int, float):
            try:
                return number(text)
            except ValueError:
                pass
        raise ValueError("a number")
    if kind == "boolean":
        if text.lower() not in ("true", "false"):
            raise ValueError("true or false")
        return text.lower() == "true"
    return text


def _typed(typed: list[str]) -> set[str]:
    """The names the author gave, even ones refused for their value."""
    return {entry.partition("=")[0] for entry in typed if "=" in entry}
