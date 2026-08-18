"""Verify the OpenSandbox capabilities required by artifacts phase 2."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from datetime import timedelta

from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox, SandboxManager
from opensandbox.config import ConnectionConfig
from opensandbox.models import NetworkPolicy, SandboxFilter


def _elapsed(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


async def run_spike(args: argparse.Namespace) -> dict[str, object]:
    # Sandbox endpoints are host-published ports behind docker.host_ip, which a
    # host-run client cannot resolve. Proxying through the server derives the
    # endpoint from however we reached the API, so one server config fits both.
    config = ConnectionConfig(
        domain=args.domain,
        api_key=args.api_key,
        use_server_proxy=True,
    )
    thread_marker = f"spike-{uuid.uuid4()}"
    sandbox: Sandbox | None = None
    connected: Sandbox | None = None

    try:
        started_at = time.perf_counter()
        sandbox = await Sandbox.create(
            args.image,
            connection_config=config,
            entrypoint=["/opt/code-interpreter/code-interpreter.sh"],
            env={"PYTHON_VERSION": "3.12"},
            metadata={"surfsense_thread": thread_marker},
            network_policy=NetworkPolicy(default_action="deny"),
            resource={"cpu": "1", "memory": "2Gi"},
            timeout=timedelta(minutes=15),
        )
        create_ms = _elapsed(started_at)

        interpreter = await CodeInterpreter.create(sandbox=sandbox)
        warm_exec_ms: list[float] = []
        for index in range(5):
            started_at = time.perf_counter()
            execution = await interpreter.codes.run(
                f"counter = globals().get('counter', 0) + 1\nprint(counter)\n{index}",
                language=SupportedLanguage.PYTHON,
            )
            if execution.error:
                raise RuntimeError(str(execution.error))
            warm_exec_ms.append(_elapsed(started_at))

        await interpreter.codes.run(
            """
from reportlab.pdfgen import canvas
c = canvas.Canvas("/tmp/spike.pdf")
c.drawString(72, 720, "SurfSense OpenSandbox spike")
c.save()
""",
            language=SupportedLanguage.PYTHON,
        )
        started_at = time.perf_counter()
        pdf_bytes = await sandbox.files.read_bytes("/tmp/spike.pdf")
        read_ms = _elapsed(started_at)
        if not pdf_bytes.startswith(b"%PDF"):
            raise RuntimeError("sandbox file read did not return a PDF")

        manager = await SandboxManager.create(connection_config=config)
        page = await manager.list_sandbox_infos(
            SandboxFilter(metadata={"surfsense_thread": thread_marker})
        )
        match = next(
            (info for info in page.sandbox_infos if info.id == sandbox.id),
            None,
        )
        if match is None:
            raise RuntimeError("metadata-filtered session rediscovery failed")

        connected = await Sandbox.connect(sandbox.id, connection_config=config)
        await connected.renew(timedelta(minutes=15))

        return {
            "sandbox_id": sandbox.id,
            "image": args.image,
            "create_ms": create_ms,
            "warm_exec_ms": warm_exec_ms,
            "warm_exec_median_ms": round(statistics.median(warm_exec_ms[1:]), 2),
            "read_bytes": len(pdf_bytes),
            "read_ms": read_ms,
            "rediscovery": "passed",
            "renew": "passed",
        }
    finally:
        if connected is not None:
            await connected.kill()
        elif sandbox is not None:
            await sandbox.kill()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="localhost:8080")
    parser.add_argument("--api-key", default="surfsense-dev-sandbox")
    parser.add_argument("--image", default="surfsense/sandbox:dev")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_spike(args)), indent=2))


if __name__ == "__main__":
    main()
