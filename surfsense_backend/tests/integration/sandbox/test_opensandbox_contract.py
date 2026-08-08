"""Live provider contract; opt in with OPENSANDBOX_INTEGRATION=1."""

from __future__ import annotations

import os
import subprocess
from mimetypes import guess_type

import pytest

from app.config import config as app_config
from app.sandbox.providers.opensandbox import OpenSandboxProvider

# Matches the tag docker-compose.dev.yml builds for the sandbox-image service.
DEV_SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "surfsense-sandbox:dev")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("OPENSANDBOX_INTEGRATION") != "1",
        reason="requires the local OpenSandbox compose service",
    ),
]


@pytest.mark.parametrize(
    ("skill", "prompt", "expected_mime", "expected_evidence_steps"),
    [
        (
            "pdf",
            "Create a one-page PDF listing three facts about X.",
            "application/pdf",
            ("check_pdf.py", "render_pages.sh"),
        )
    ],
)
async def test_opensandbox_persistent_kernel_binary_io_and_terminate(
    monkeypatch, skill, prompt, expected_mime, expected_evidence_steps
):
    monkeypatch.setattr(app_config, "OPENSANDBOX_DOMAIN", "localhost:8080")
    monkeypatch.setattr(
        app_config, "OPENSANDBOX_API_KEY", "surfsense-dev-sandbox"
    )
    monkeypatch.setattr(app_config, "SANDBOX_IMAGE", DEV_SANDBOX_IMAGE)
    monkeypatch.setattr(app_config, "SANDBOX_IDLE_TTL_SECONDS", 900)
    provider = OpenSandboxProvider()
    thread_id = "pytest-opensandbox-contract"

    await provider.terminate_session(thread_id)
    session = await provider.get_or_create_session(thread_id)
    try:
        evidence: list[str] = []
        first = await session.execute("contract_value = 41\nprint(contract_value)")
        second = await session.execute("print(contract_value + 1)")
        pdf = await session.execute(
            """
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
c = canvas.Canvas("/tmp/three-facts.pdf")
c.setFont("DejaVu", 12)
for y, fact in zip((740, 710, 680), ("Fact one", "Fact two", "Fact three")):
    c.drawString(72, y, fact)
c.save()
"""
        )
        checked = await session.run_command(
            f"/opt/skills/{skill}/scripts/check_pdf.py /tmp/three-facts.pdf"
        )
        evidence.append("check_pdf.py")
        rendered = await session.run_command(
            f"/opt/skills/{skill}/scripts/render_pages.sh "
            "/tmp/three-facts.pdf /tmp/three-facts-pages"
        )
        evidence.append("render_pages.sh")
        pdf_data = await session.read_file("/tmp/three-facts.pdf")
        jpeg_data = await session.read_file("/tmp/three-facts-pages/page-1.jpg")
        await session.write_file("/tmp/contract.bin", b"\x00SurfSense")
        data = await session.read_file("/tmp/contract.bin")
        stat = await session.run_command("stat -c %s /tmp/contract.bin")

        assert first.ok and "41" in first.output
        assert second.ok and "42" in second.output
        assert pdf.ok and rendered.ok and checked.ok
        assert prompt
        assert guess_type("/tmp/three-facts.pdf")[0] == expected_mime
        assert tuple(evidence) == expected_evidence_steps
        assert pdf_data.startswith(b"%PDF")
        assert jpeg_data.startswith(b"\xff\xd8")
        assert data == b"\x00SurfSense"
        assert int(stat.output.strip()) == len(data)
    finally:
        await provider.terminate_session(thread_id)


def _compose_ip(container: str) -> str:
    probe = subprocess.run(
        ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", container],
        capture_output=True,
        text=True,
    )
    addresses = probe.stdout.split()
    if probe.returncode != 0 or not addresses:
        pytest.skip(f"cannot resolve {container} on the compose network")
    return addresses[0]


async def test_sandbox_cannot_reach_the_compose_network(monkeypatch):
    """Egress deny has to hold for raw IPs, not only for hostnames.

    `[egress] mode = "dns"` filters hostnames through a DNS proxy and installs
    no packet filter, so a sandbox could open Postgres at its container IP and
    log in with the default credentials. Only `dns+nft` enforces the policy at
    the network layer, and nothing about the config reads as broken, so the
    connection has to actually be attempted for the regression to be visible.
    """
    monkeypatch.setattr(app_config, "OPENSANDBOX_DOMAIN", "localhost:8080")
    monkeypatch.setattr(app_config, "OPENSANDBOX_API_KEY", "surfsense-dev-sandbox")
    monkeypatch.setattr(app_config, "SANDBOX_IMAGE", DEV_SANDBOX_IMAGE)
    db_ip = _compose_ip(os.getenv("OPENSANDBOX_DB_CONTAINER", "surfsense-dev-db-1"))

    provider = OpenSandboxProvider()
    thread_id = "pytest-opensandbox-egress"
    await provider.terminate_session(thread_id)
    session = await provider.get_or_create_session(thread_id)
    try:
        # Distinguishes "policy blocks it" from "the sandbox runs nothing".
        assert (await session.run_command("echo reachable")).ok

        connect = await session.run_command(
            'python3 -c "import socket,sys;s=socket.socket();s.settimeout(5);'
            f"sys.exit(s.connect_ex(('{db_ip}',5432)))\""
        )
        assert not connect.ok, f"sandbox opened Postgres at {db_ip}:5432"
    finally:
        await provider.terminate_session(thread_id)
