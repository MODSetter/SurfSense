"""What an engine did with each operation, for the model, the user and the stored version."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["applied", "refused", "skipped"]
Values = dict[str, str | int]


@dataclass(frozen=True)
class OpOutcome:
    index: int
    op: str
    status: Status
    code: str | None
    values: Values = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True)
class Notice:
    code: str
    values: Values
    message: str


@dataclass(frozen=True)
class Report:
    saved: bool
    outcomes: tuple[OpOutcome, ...]
    must_tell_user: tuple[Notice, ...]
    input_sha256: str
    output_sha256: str | None

    @property
    def applied(self) -> int:
        return self._count("applied")

    @property
    def refused(self) -> int:
        return self._count("refused")

    @property
    def skipped(self) -> int:
        return self._count("skipped")

    def _count(self, status: Status) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == status)

    def as_metadata(self) -> dict[str, Any]:
        return {
            "schema": "revise-report/1",
            "saved": self.saved,
            "ops": [
                {
                    "index": o.index,
                    "op": o.op,
                    "status": o.status,
                    "code": o.code,
                    "values": dict(o.values),
                    "message": o.message,
                }
                for o in self.outcomes
            ],
            "applied": self.applied,
            "refused": self.refused,
            "skipped": self.skipped,
            "must_tell_user": [
                {"code": n.code, "values": dict(n.values), "message": n.message}
                for n in self.must_tell_user
            ],
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
        }

    def as_text(self) -> str:
        lines = []
        for o in self.outcomes:
            if o.status == "applied":
                lines.append(f"#{o.index} {o.op}: applied.")
            else:
                lines.append(f"#{o.index} {o.op} {o.status} ({o.code}): {o.message}")
        lines.extend(f"Note ({n.code}): {n.message}" for n in self.must_tell_user)
        return "\n".join(lines)


def op_name(operation: object) -> str:
    """The op's name as sent, or `?` when there is none to name."""
    if isinstance(operation, dict) and isinstance(operation.get("op"), str):
        return operation["op"]
    return "?"


def applied(index: int, op: str, values: Values | None = None) -> OpOutcome:
    return OpOutcome(index, op, "applied", None, values or {}, "")


def refused(index: int, op: str, code: str, values: Values, message: str) -> OpOutcome:
    return OpOutcome(index, op, "refused", code, values, message)


def bad_operation(index: int, op: str, field_name: str, why: str) -> OpOutcome:
    return refused(
        index, op, "BAD_OPERATION", {"field": field_name}, f"{field_name}: {why}"
    )


def unsupported(index: int, op: str, format_name: str) -> OpOutcome:
    return refused(
        index,
        op,
        "UNSUPPORTED_OPERATION",
        {"op": op, "format": format_name},
        f"{op} is not an operation for a .{format_name} file.",
    )


def skip_others(
    operations: Sequence[object], refusal: OpOutcome
) -> tuple[OpOutcome, ...]:
    """All or nothing: the refusal stands, every other operation is skipped unsaved."""
    return tuple(
        refusal
        if index == refusal.index
        else OpOutcome(
            index,
            op_name(operation),
            "skipped",
            "BATCH_REFUSED",
            {"index": refusal.index},
            f"Nothing was saved because #{refusal.index} was refused.",
        )
        for index, operation in enumerate(operations)
    )


def nothing_changed() -> Notice:
    return Notice(
        "NOTHING_CHANGED",
        {},
        "The operations left the file as it was, so no copy was saved.",
    )
