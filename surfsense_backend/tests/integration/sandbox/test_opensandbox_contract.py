"""Live provider contract; opt in with OPENSANDBOX_INTEGRATION=1."""

from __future__ import annotations

import os

import pytest

from app.config import config as app_config
from app.sandbox.providers.opensandbox import OpenSandboxProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("OPENSANDBOX_INTEGRATION") != "1",
        reason="requires the local OpenSandbox compose service",
    ),
]


async def test_opensandbox_persistent_kernel_binary_io_and_terminate(monkeypatch):
    monkeypatch.setattr(app_config, "OPENSANDBOX_DOMAIN", "localhost:8080")
    monkeypatch.setattr(
        app_config, "OPENSANDBOX_API_KEY", "surfsense-dev-sandbox"
    )
    monkeypatch.setattr(app_config, "SANDBOX_IMAGE", "surfsense/sandbox:dev")
    monkeypatch.setattr(app_config, "SANDBOX_IDLE_TTL_SECONDS", 900)
    provider = OpenSandboxProvider()
    thread_id = "pytest-opensandbox-contract"

    await provider.terminate_session(thread_id)
    session = await provider.get_or_create_session(thread_id)
    try:
        first = await session.execute("contract_value = 41\nprint(contract_value)")
        second = await session.execute("print(contract_value + 1)")
        pdf = await session.execute(
            """
from reportlab.pdfgen import canvas
c = canvas.Canvas("/tmp/three-facts.pdf")
for y, fact in zip((740, 710, 680), ("Fact one", "Fact two", "Fact three")):
    c.drawString(72, y, fact)
c.save()
"""
        )
        rendered = await session.run_command(
            "/opt/skills/pdf/scripts/render_pages.sh "
            "/tmp/three-facts.pdf /tmp/three-facts-pages"
        )
        checked = await session.run_command(
            "/opt/skills/pdf/scripts/check_pdf.py /tmp/three-facts.pdf"
        )
        pdf_data = await session.read_file("/tmp/three-facts.pdf")
        jpeg_data = await session.read_file("/tmp/three-facts-pages/page-1.jpg")
        await session.write_file("/tmp/contract.bin", b"\x00SurfSense")
        data = await session.read_file("/tmp/contract.bin")
        stat = await session.run_command("stat -c %s /tmp/contract.bin")

        assert first.ok and "41" in first.output
        assert second.ok and "42" in second.output
        assert pdf.ok and rendered.ok and checked.ok
        assert pdf_data.startswith(b"%PDF")
        assert jpeg_data.startswith(b"\xff\xd8")
        assert data == b"\x00SurfSense"
        assert int(stat.output.strip()) == len(data)
    finally:
        await provider.terminate_session(thread_id)
