"""A document script checked before it runs: the brackets fixed where only they are off, any
other syntax error sent back with its line, a caret and a hint.

Small models leave a closing bracket out of a long table or chart call, and a run that
fails only says where Python gave up. Closing what is left open costs nothing and the
note says what changed; anything else stays the model's to fix, but it learns where
and how without a run.
"""

import ast
import io
import re
import tokenize

__all__ = ["ScriptSyntaxError", "checked_script"]

_OPEN = {"(": ")", "[": "]", "{": "}"}
_CLOSE = {v: k for k, v in _OPEN.items()}
_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*\n(.*?)\n\s*```\s*$", re.S)
_HINTS = (
    (
        "was never closed",
        "a bracket opened on this line is never closed: close it where its expression ends",
    ),
    (
        "does not match opening",
        "this closing bracket is not the one the line above left open: close the inner "
        "one first, as in `])` rather than `)`",
    ),
    (
        "unmatched",
        "this closing bracket has no opening one: remove it or add the opening bracket",
    ),
    ("unterminated string", "a string on this line has no closing quote"),
    ("unterminated triple-quoted", "a triple-quoted string is never closed"),
    ("expected ':'", "add the colon this line needs"),
    ("indent", "indent this block with four spaces, the same as the lines around it"),
    (
        "invalid syntax",
        "look for a missing comma, bracket or quote just before the caret",
    ),
)


class ScriptSyntaxError(ValueError):
    """The script cannot run; the message is what the model needs to fix it."""


def checked_script(script: str) -> tuple[str, str | None]:
    """The script to run and a note of any fix made; raises `ScriptSyntaxError`
    when it cannot be fixed."""
    notes: list[str] = []
    fenced = _FENCE.match(script)
    if fenced:
        script = fenced.group(1)
        notes.append("removed the Markdown fence around the script")
    try:
        ast.parse(script)
        return script, _note(notes)
    except SyntaxError as first:
        fixed, changes = _balanced(script)
        if fixed is not None:
            try:
                ast.parse(fixed)
                return fixed, _note(notes + changes)
            except SyntaxError:
                pass
        raise ScriptSyntaxError(_explain(script, first)) from first


def _note(changes: list[str]) -> str | None:
    if not changes:
        return None
    return (
        "Before running the script, SurfSense "
        + "; ".join(changes)
        + ". Check that the result is what you meant."
    )


def _balanced(script: str) -> tuple[str | None, list[str]]:
    """The script with missing closing brackets added, or None when that is not
    the problem."""
    stack: list[tuple[str, int]] = []
    inserts: list[tuple[int, int, str]] = []
    changes: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(script).readline):
            if tok.type != tokenize.OP:
                continue
            if tok.string in _OPEN:
                stack.append((tok.string, tok.start[0]))
            elif tok.string in _CLOSE:
                want = _CLOSE[tok.string]
                if stack and stack[-1][0] == want:
                    stack.pop()
                elif any(o == want for o, _ in stack):
                    missing = ""
                    while stack[-1][0] != want:
                        o, line = stack.pop()
                        missing += _OPEN[o]
                        changes.append(
                            f"closed the {o} opened on line {line} before the "
                            f"{tok.string} on line {tok.start[0]}"
                        )
                    stack.pop()
                    inserts.append((tok.start[0], tok.start[1], missing))
                else:
                    return None, []
    except tokenize.TokenError:
        pass  # the end of the file inside an open bracket: closed below
    except (IndentationError, SyntaxError):
        return None, []
    lines = script.splitlines(keepends=True)
    for row, col, text in sorted(inserts, reverse=True):
        lines[row - 1] = lines[row - 1][:col] + text + lines[row - 1][col:]
    out = "".join(lines)
    if stack:
        out = out.rstrip() + "".join(_OPEN[o] for o, _ in reversed(stack)) + "\n"
        changes += [
            f"closed the {o} opened on line {line} at the end of the script"
            for o, line in stack
        ]
    return (out, changes) if changes else (None, [])


def _explain(script: str, error: SyntaxError) -> str:
    lines = script.splitlines()
    n = error.lineno or 1
    message = (error.msg or "invalid syntax").strip()
    shown = []
    for k in range(max(1, n - 2), min(len(lines), n + 2) + 1):
        shown.append(f"{'>' if k == n else ' '} {k:4d} | {lines[k - 1]}")
        if k == n and error.offset:
            shown.append(" " * (9 + error.offset) + "^")
    hint = next(
        (h for key, h in _HINTS if key in message), "fix the line the caret points at"
    )
    return (
        f"The script does not parse, so it was not run. Line {n}: {message}.\n"
        + "\n".join(shown)
        + f"\nHint: {hint}. Fix it and render again."
    )
