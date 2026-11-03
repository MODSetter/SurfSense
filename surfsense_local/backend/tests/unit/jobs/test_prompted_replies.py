"""A model held to no schema, as Claude is through Anthropic's OpenAI-compatible API, is shown
the schema in its prompt, and its reply is read in the shapes it gives."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from modules.jobs.workbook_rows.ask import parse_draft
from modules.jobs.workbook_rows.config import load_config
from tests.job_pack_samples import JOB, write_questionnaire_pack
from worker.studio.job_run import pipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def config(tmp_path: Path):
    """The sample pack's job, allowing three quotes."""
    pack = write_questionnaire_pack(tmp_path / "pack")
    job = pack / "jobs" / JOB / "job.json"
    raw = json.loads(job.read_text(encoding="utf-8"))
    raw["max_quotes"] = 3
    job.write_text(json.dumps(raw), encoding="utf-8")
    return load_config(job)


def test_quotes_given_as_strings_take_their_passages_from_the_list_beside_them(config):
    """`"quotes": ["a", "b"], "passage": [6, 9]` reads as two quotes, from passages 6 and 9."""
    draft = parse_draft(
        json.dumps(
            {
                "quotes": ["Access is granted on need.", "Logs are kept a year."],
                "passage": [6, 9],
                "answer": "Yes",
                "comment": "",
                "confidence": "high",
            }
        ),
        config,
    )

    assert draft is not None
    assert [(q.passage, q.quote) for q in draft.quotes] == [
        (6, "Access is granted on need."),
        (9, "Logs are kept a year."),
    ]


def test_a_single_quote_reads_as_one(config):
    """The flat `quote` and `passage` fields of a reply that ignored the list still count."""
    draft = parse_draft(
        json.dumps(
            {
                "quote": "Access is granted on need.",
                "passage": 4,
                "answer": "Yes",
                "comment": "",
                "confidence": "high",
            }
        ),
        config,
    )

    assert draft is not None
    assert [(q.passage, q.quote) for q in draft.quotes] == [
        (4, "Access is granted on need.")
    ]


def test_an_endpoint_that_refuses_the_schema_is_shown_it_in_the_prompt(monkeypatch):
    """After the first refusal, every call carries the schema in its system message instead."""
    sent: list[tuple[list, dict | None]] = []

    def complete(model, messages, *, max_tokens, json_schema=None, conversation=None):
        sent.append((messages, json_schema))
        if json_schema is not None:
            raise httpx.HTTPStatusError(
                "response_format.json_schema.strict: Field required",
                request=httpx.Request("POST", "https://example.test"),
                response=httpx.Response(400),
            )
        return '{"supported": true, "missing": ""}'

    monkeypatch.setattr(pipeline, "complete", complete)
    selection = SimpleNamespace(name="claude-sonnet-5-5", provider="anthropic")
    model = pipeline.SelectedModel(SimpleNamespace(selection=selection), 200_000)
    schema = {"type": "object", "properties": {"supported": {"type": "boolean"}}}

    first = model.ask("Check the answer.", [("user", "Question: ...")], schema, 0)
    second = model.ask("Check the answer.", [("user", "Question: ...")], schema, 0)

    assert first.text == second.text == '{"supported": true, "missing": ""}'
    assert [s is None for _, s in sent] == [False, True, True]
    for messages, _ in sent[1:]:
        assert messages[0].content.startswith("Check the answer.")
        assert json.dumps(schema) in messages[0].content


def _model(monkeypatch, replies):
    """The worker's model over a scripted `complete`: each item is raised, or returned."""
    queue = list(replies)

    def complete(model, messages, *, max_tokens, json_schema=None, conversation=None):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(pipeline, "complete", complete)
    monkeypatch.setattr(pipeline.time, "sleep", lambda seconds: None)
    selection = SimpleNamespace(name="qwen/qwen3.8-27b", provider="openrouter")
    return pipeline.SelectedModel(SimpleNamespace(selection=selection), 131_072), queue


def test_a_stalled_stream_is_tried_again_and_then_left_to_a_person(monkeypatch):
    """A stall is tried again; one that never answers gives an empty reply rather than
    failing the whole run."""
    from modules.llm.providers.stream_deadline import StreamTimeoutError

    stall = StreamTimeoutError(30, first_item=False, subject="the model")
    model, _ = _model(monkeypatch, [stall, '{"answer": "Yes"}'])
    assert model.ask("s", [("user", "q")], {}, 0).text == '{"answer": "Yes"}'

    model, left = _model(monkeypatch, [stall] * pipeline.TRIES)
    assert model.ask("s", [("user", "q")], {}, 0).text == ""
    assert left == []


def test_a_refused_key_still_fails_the_run(monkeypatch):
    """An error that trying again cannot fix is raised, so a run never ends blank in silence."""
    unauthorized = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(401),
    )
    model, _ = _model(monkeypatch, [unauthorized])

    with pytest.raises(httpx.HTTPStatusError):
        model.ask("s", [("user", "q")], {}, 0)


def test_a_rate_limit_waits_as_long_as_the_provider_asks(monkeypatch):
    """A 429's Retry-After is followed, within a minute, before the call is tried again."""
    limited = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(429, headers={"Retry-After": "7"}),
    )
    model, _ = _model(monkeypatch, [limited, '{"answer": "Yes"}'])
    pauses: list[float] = []
    monkeypatch.setattr(pipeline.time, "sleep", pauses.append)

    assert model.ask("s", [("user", "q")], {}, 0).text == '{"answer": "Yes"}'
    assert pauses == [7.0]
    assert pipeline._pause(limited, 0) == 7.0
    too_long = httpx.HTTPStatusError(
        "429",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(429, headers={"Retry-After": "3600"}),
    )
    assert pipeline._pause(too_long, 0) == pipeline.MAX_RETRY_AFTER_SECONDS
