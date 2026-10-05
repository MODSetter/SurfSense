"""Images attached to a chat turn: what the model receives, what is kept, what goes."""

import base64
import io
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image as Pillow
from sqlalchemy import Engine

from tests.integration.chat.conftest import set_props_n_ctx, set_sees
from tests.integration.chat.test_chat import _open_thread, _seed

pytestmark = pytest.mark.integration


def picture(color: str = "navy") -> dict:
    """One attachment as the composer sends it."""
    out = io.BytesIO()
    Pillow.new("RGB", (64, 48), color).save(out, format="PNG")
    return {"mime": "image/png", "data": base64.b64encode(out.getvalue()).decode()}


async def send(client: AsyncClient, thread_id: int, text: str, images: list[dict]):
    """Post a turn and drain its stream; the status line is the caller's to check."""
    async with client.stream(
        "POST",
        f"/chat/threads/{thread_id}/messages",
        json={"text": text, "images": images},
    ) as reply:
        body = [line async for line in reply.aiter_lines()]
    return reply.status_code, body


def image_parts(message: dict) -> list[dict]:
    """The image parts of one sent message; none when its content is a string."""
    content = message["content"]
    if isinstance(content, str):
        return []
    return [part for part in content if part["type"] == "image_url"]


def stored_images(data_dir: Path) -> list[Path]:
    """Every chat image file on disk."""
    return sorted((data_dir / "data").rglob("chats/*/*"))


async def test_a_model_that_sees_receives_the_image_and_the_turn_keeps_it(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
) -> None:
    """The model gets typed parts; the row keeps a reference and the file is served back."""
    set_sees(True)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    status, _ = await send(client, thread_id, "what is this?", [picture()])

    assert status == 200
    asked = llamacpp_server[-1]["messages"][-1]
    assert asked["content"][0] == {"type": "text", "text": "what is this?"}
    (part,) = image_parts(asked)
    assert part["image_url"]["url"].startswith("data:image/jpeg;base64,")

    user, _assistant = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    (ref,) = user["content"]["images"]
    assert ref["mime"] == "image/jpeg"
    served = await client.get(
        f"/chat/threads/{thread_id}/messages/{user['id']}/images/0"
    )
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert len(stored_images(data_dir)) == 1


async def test_a_model_that_cannot_see_is_refused_and_nothing_is_kept(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
) -> None:
    """A 409 before anything is stored, so the composer can say why."""
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    status, body = await send(client, thread_id, "what is this?", [picture()])

    assert status == 409
    assert "can't read images" in json.loads("".join(body))["detail"]
    assert (await client.get(f"/chat/threads/{thread_id}/messages")).json() == []
    assert stored_images(data_dir) == []
    assert llamacpp_server == []


async def test_images_that_outgrow_the_window_are_refused_and_nothing_is_kept(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
) -> None:
    """2,048 tokens hold at most four 256-token images once the answer is
    reserved, fewer with the turn's text: four overflow even at 256 each."""
    set_sees(True)
    set_props_n_ctx(2048)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    status, body = await send(client, thread_id, "what are these?", [picture()] * 4)

    assert status == 409
    assert "Send fewer" in json.loads("".join(body))["detail"]
    assert (await client.get(f"/chat/threads/{thread_id}/messages")).json() == []
    assert stored_images(data_dir) == []
    assert llamacpp_server == []


async def test_images_a_cheap_projector_fits_are_sent(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
) -> None:
    """Three images on an 8,192 window cost 768 on Gemma 3, so they are sent,
    though the history trim prices each at 1,400."""
    set_sees(True)
    set_props_n_ctx(8192)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    status, _ = await send(client, thread_id, "what are these?", [picture()] * 3)

    assert status == 200
    assert len(image_parts(llamacpp_server[-1]["messages"][-1])) == 3


async def test_bytes_that_are_not_an_image_are_refused(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The bytes decide, whatever the claimed type says."""
    set_sees(True)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)
    fake = {"mime": "image/png", "data": base64.b64encode(b"%PDF-1.7").decode()}

    status, _ = await send(client, thread_id, "what is this?", [fake])

    assert status == 422
    assert (await client.get(f"/chat/threads/{thread_id}/messages")).json() == []


async def test_more_than_four_images_are_refused(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A turn carries at most four."""
    set_sees(True)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    status, _ = await send(client, thread_id, "compare", [picture()] * 5)

    assert status == 422


async def test_a_followup_resends_only_the_newest_image_turn(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """ "And the left axis?" still reaches a model that has the picture, and an
    older picture it already answered about is not paid for again."""
    set_sees(True)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)
    await send(client, thread_id, "first chart", [picture("red")])
    await send(client, thread_id, "second chart", [picture("blue")])
    llamacpp_server.clear()

    await send(client, thread_id, "and the left axis?", [])

    sent = llamacpp_server[-1]["messages"]
    with_images = [m for m in sent if image_parts(m)]
    assert [m["content"][0]["text"] for m in with_images] == ["second chart"]
    assert "first chart" in [m["content"] for m in sent]
    assert sent[-1] == {"role": "user", "content": "and the left axis?"}


async def test_deleting_a_thread_removes_its_images(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
) -> None:
    """Its folder goes after the commit."""
    set_sees(True)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)
    await send(client, thread_id, "what is this?", [picture()])

    await client.delete(f"/chat/threads/{thread_id}")

    assert stored_images(data_dir) == []


async def test_a_failed_reply_leaves_no_image_behind(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server_unauthorized: None,
    data_dir: Path,
) -> None:
    """The turn is discarded, and so is the file only it referenced. The
    runtime could not be asked whether the model sees, so the turn was let
    through and failed on its own terms."""
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    status, _ = await send(client, thread_id, "what is this?", [picture()])

    assert status == 200
    assert (await client.get(f"/chat/threads/{thread_id}/messages")).json() == []
    assert stored_images(data_dir) == []
