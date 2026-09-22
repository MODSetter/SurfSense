"""What Hugging Face already knows, asked before anything is downloaded.

The listing API parses the first GGUF's header and serves the result, so the
architecture and the chat template are free. Reading them first means a model
llama.cpp cannot run costs no range request against a file nobody will install.
"""

import httpx
import pytest

from modules.llm.catalog.search import read_repo_facts

pytestmark = pytest.mark.unit

GGUF = {
    "total": 8_190_735_360,
    "architecture": "qwen3",
    "context_length": 40960,
    "chat_template": "{%- if tools %}...{%- endif %}",
    "eos_token": "<|im_end|>",
}


def serving(payload: object, status: int = 200) -> httpx.MockTransport:
    """A transport answering the listing call and nothing else."""
    return httpx.MockTransport(lambda request: httpx.Response(status, json=payload))


async def test_the_parsed_header_the_listing_already_holds_is_read() -> None:
    """Architecture, window and template, with no bytes of the model fetched."""
    async with httpx.AsyncClient(transport=serving({"gguf": GGUF})) as client:
        facts = await read_repo_facts(client, "unsloth/Qwen3-8B-GGUF")

    assert facts is not None
    assert facts.architecture == "qwen3"
    assert facts.context_length == 40960
    assert facts.has_chat_template


async def test_a_model_with_no_chat_template_is_reported_as_such() -> None:
    """Installable, but it will answer badly in a chat, so the screen warns."""
    payload = {"gguf": {**GGUF, "chat_template": ""}}
    async with httpx.AsyncClient(transport=serving(payload)) as client:
        facts = await read_repo_facts(client, "some/repo")

    assert facts is not None
    assert not facts.has_chat_template


async def test_a_repo_hugging_face_has_not_parsed_is_not_a_refusal() -> None:
    """None means "ask the file yourself", not "this repo is bad"."""
    async with httpx.AsyncClient(transport=serving({})) as client:
        assert await read_repo_facts(client, "some/repo") is None


async def test_a_listing_that_fails_is_not_a_refusal_either() -> None:
    """The header read is still available, and it is the authoritative one."""
    async with httpx.AsyncClient(transport=serving({}, status=500)) as client:
        assert await read_repo_facts(client, "some/repo") is None


async def test_the_pipeline_tag_is_read_in_the_same_call() -> None:
    """A model built on a chat architecture and then trained to do something
    else is invisible to the header gate. Measured: `Nemotron-3-Embed-1B`
    declares `mistral3` and tags itself `sentence-similarity`.

    It rides along on the call already being made, so the check costs no extra
    round trip.
    """
    seen: list[httpx.URL] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(
            200, json={"gguf": GGUF, "pipeline_tag": "sentence-similarity"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        facts = await read_repo_facts(client, "some/embed-gguf")

    assert facts is not None
    assert facts.pipeline_tag == "sentence-similarity"
    assert len(seen) == 1
    assert "pipeline_tag" in str(seen[0])


async def test_an_untagged_repo_reports_no_tag_rather_than_failing() -> None:
    """Roughly four fifths of GGUF repos carry no tag, so the common case has
    to be a quiet None and not a refusal."""
    async with httpx.AsyncClient(transport=serving({"gguf": GGUF})) as client:
        facts = await read_repo_facts(client, "some/repo")

    assert facts is not None
    assert facts.pipeline_tag is None
