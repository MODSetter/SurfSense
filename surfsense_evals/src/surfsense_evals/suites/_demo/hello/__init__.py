"""Demo benchmark — registers on import, used only by the registry tests."""

from __future__ import annotations

import argparse
from typing import Any

from ....core.registry import (
    Benchmark,
    ReportSection,
    RunArtifact,
    RunContext,
    register,
)


class HelloBenchmark:
    suite: str = "_demo"
    name: str = "hello"
    headline: bool = False
    description: str = "Demo benchmark used by the registry test."

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--echo", default="hi")

    async def ingest(self, ctx: RunContext, **_opts: Any) -> None:  # pragma: no cover
        return None

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:  # pragma: no cover
        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp="0",
            raw_path=ctx.benchmark_data_dir() / "raw.jsonl",
            metrics={"echo": opts.get("echo")},
        )

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        return ReportSection(
            title="Hello demo",
            headline=False,
            body_md="- runs: " + str(len(artifacts)),
        )


register(HelloBenchmark())
