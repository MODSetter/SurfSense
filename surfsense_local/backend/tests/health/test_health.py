from httpx import AsyncClient


async def test_health_reports_ok(client: AsyncClient) -> None:
    """Electron gates its window on this probe, so the body is a fixed contract."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
