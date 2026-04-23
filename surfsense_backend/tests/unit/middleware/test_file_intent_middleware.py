import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.new_chat.middleware.file_intent import (
    FileIntentMiddleware,
    FileOperationIntent,
)

pytestmark = pytest.mark.unit


class _FakeLLM:
    def __init__(self, response_text: str):
        self._response_text = response_text

    async def ainvoke(self, *_args, **_kwargs):
        return AIMessage(content=self._response_text)


@pytest.mark.asyncio
async def test_file_write_intent_injects_contract_message():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.93,"suggested_filename":"ideas.md"}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="Create another random note for me")],
        "turn_id": "123:456",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/ideas.md"
    assert contract["turn_id"] == "123:456"
    assert any(
        "file_operation_contract" in str(msg.content)
        for msg in result["messages"]
        if hasattr(msg, "content")
    )


@pytest.mark.asyncio
async def test_non_write_intent_does_not_inject_contract_message():
    llm = _FakeLLM(
        '{"intent":"file_read","confidence":0.88,"suggested_filename":null}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    original_messages = [HumanMessage(content="Read /notes.md")]
    state = {"messages": original_messages, "turn_id": "abc:def"}

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    assert result["file_operation_contract"]["intent"] == FileOperationIntent.FILE_READ.value
    assert "messages" not in result


@pytest.mark.asyncio
async def test_file_write_null_filename_uses_semantic_default_path():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.74,"suggested_filename":null}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="create a random markdown file")],
        "turn_id": "turn:1",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/notes.md"


@pytest.mark.asyncio
async def test_file_write_null_filename_infers_json_extension():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.71,"suggested_filename":null}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="create a sample json config file")],
        "turn_id": "turn:2",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/notes.json"


@pytest.mark.asyncio
async def test_file_write_txt_suggestion_is_normalized_to_markdown():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.82,"suggested_filename":"random.txt"}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="create a random file")],
        "turn_id": "turn:3",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/random.md"

