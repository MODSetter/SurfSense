import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.new_chat.middleware.file_intent import (
    FileIntentMiddleware,
    FileOperationIntent,
    _fallback_path,
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
    llm = _FakeLLM('{"intent":"file_read","confidence":0.88,"suggested_filename":null}')
    middleware = FileIntentMiddleware(llm=llm)
    original_messages = [HumanMessage(content="Read /notes.md")]
    state = {"messages": original_messages, "turn_id": "abc:def"}

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    assert (
        result["file_operation_contract"]["intent"]
        == FileOperationIntent.FILE_READ.value
    )
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
async def test_file_write_null_filename_defaults_to_markdown_path():
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
    assert contract["suggested_path"] == "/notes.md"


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


@pytest.mark.asyncio
async def test_file_write_with_suggested_directory_preserves_folder():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.86,"suggested_filename":"random.md","suggested_directory":"pc backups","suggested_path":null}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="create a random file in pc backups folder")],
        "turn_id": "turn:4",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/pc_backups/random.md"


@pytest.mark.asyncio
async def test_file_write_with_suggested_path_takes_precedence():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.9,"suggested_filename":"ignored.md","suggested_directory":"docs","suggested_path":"/reports/q2/summary.md"}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="create report")],
        "turn_id": "turn:5",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/reports/q2/summary.md"


@pytest.mark.asyncio
async def test_file_write_infers_directory_from_user_text_when_missing():
    llm = _FakeLLM(
        '{"intent":"file_write","confidence":0.83,"suggested_filename":"random.md","suggested_directory":null,"suggested_path":null}'
    )
    middleware = FileIntentMiddleware(llm=llm)
    state = {
        "messages": [HumanMessage(content="create a random file in pc backups folder")],
        "turn_id": "turn:6",
    }

    result = await middleware.abefore_agent(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None
    contract = result["file_operation_contract"]
    assert contract["intent"] == FileOperationIntent.FILE_WRITE.value
    assert contract["suggested_path"] == "/pc_backups/random.md"


def test_fallback_path_normalizes_windows_slashes() -> None:
    resolved = _fallback_path(
        suggested_filename="summary.md",
        suggested_path=r"\reports\q2\summary.md",
        user_text="create report",
    )

    assert resolved == "/reports/q2/summary.md"


def test_fallback_path_normalizes_windows_drive_path() -> None:
    resolved = _fallback_path(
        suggested_filename=None,
        suggested_path=r"C:\Users\anish\notes\todo.md",
        user_text="create note",
    )

    assert resolved == "/C/Users/anish/notes/todo.md"


def test_fallback_path_normalizes_mixed_separators_and_duplicate_slashes() -> None:
    resolved = _fallback_path(
        suggested_filename="summary.md",
        suggested_path=r"\\reports\\q2//summary.md",
        user_text="create report",
    )

    assert resolved == "/reports/q2/summary.md"


def test_fallback_path_keeps_posix_style_absolute_path_for_linux_and_macos() -> None:
    resolved = _fallback_path(
        suggested_filename=None,
        suggested_path="/var/log/surfsense/notes.md",
        user_text="create note",
    )

    assert resolved == "/var/log/surfsense/notes.md"
