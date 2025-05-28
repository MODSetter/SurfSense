import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import SQLAlchemyError

from app.tasks.connectors_indexing_tasks import index_slack_messages
from app.db import SearchSourceConnector, SearchSourceConnectorType, Document, DocumentType, Chunk
from app.schemas.search_source_connector import SearchSourceConnectorCreate # For creating test connector data
from app.connectors.slack_history import SlackHistory # To mock its methods

# Mock global config object if it's accessed directly
# If it's passed around, then mock where it's used/passed.
# For this example, assuming app.config.config is used.
@pytest.fixture(autouse=True)
def mock_app_config():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test Summary"))

    mock_embedding_model = MagicMock()
    mock_embedding_model.embed = MagicMock(return_value=[0.1, 0.2, 0.3])
    
    mock_chunker = MagicMock()
    # Simulate chunker returning list of objects with a 'text' attribute
    mock_chunker.chunk = MagicMock(return_value=[MagicMock(text="chunk1"), MagicMock(text="chunk2")])

    with patch('app.config.config.long_context_llm_instance', mock_llm), \
         patch('app.config.config.embedding_model_instance', mock_embedding_model), \
         patch('app.config.config.chunker_instance', mock_chunker), \
         patch('app.config.config.SUMMARY_PROMPT_TEMPLATE', MagicMock()): # Assuming this is a simple object
        yield

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None), all=MagicMock(return_value=[])))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session

@pytest.fixture
def base_slack_connector():
    return SearchSourceConnector(
        id=1,
        user_id="test_user_1",
        search_space_id=1,
        name="Test Slack Connector",
        connector_type=SearchSourceConnectorType.SLACK_CONNECTOR,
        is_indexable=True,
        config={
            "SLACK_BOT_TOKEN": "xoxb-dummy-token",
            "slack_initial_indexing_days": 30,
            "slack_initial_max_messages_per_channel": 100,
            "slack_max_messages_per_channel_periodic": 50,
            "slack_membership_filter_type": "all_member_channels",
            "slack_selected_channel_ids": [],
            "slack_periodic_indexing_enabled": True, # New field from previous task
            "slack_periodic_indexing_frequency": "daily" # New field
        },
        last_indexed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def mock_slack_history_instance():
    instance = AsyncMock(spec=SlackHistory)
    instance.get_all_channels = AsyncMock(return_value=[])
    instance.get_conversation_history = AsyncMock(return_value=[])
    # format_message should return a dict, not an AsyncMock
    instance.format_message = MagicMock(return_value={
        "user_id": "U123", "text": "Formatted message", "datetime": "2023-01-01 10:00:00 UTC"
    })
    return instance


@pytest.mark.asyncio
async def test_connector_not_found(mock_session):
    mock_session.execute.return_value.scalars.return_value.first.return_value = None
    count, error = await index_slack_messages(mock_session, 999, 1)
    assert count == 0
    assert "Connector with ID 999 not found" in error

@pytest.mark.asyncio
async def test_connector_not_slack_type(mock_session, base_slack_connector):
    base_slack_connector.connector_type = SearchSourceConnectorType.NOTION_CONNECTOR
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    count, error = await index_slack_messages(mock_session, 1, 1)
    assert count == 0
    assert "is not a Slack connector" in error

@pytest.mark.asyncio
async def test_slack_token_missing(mock_session, base_slack_connector):
    base_slack_connector.config = {} # No token
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    count, error = await index_slack_messages(mock_session, 1, 1)
    assert count == 0
    assert "Slack token not found" in error

@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_no_channels_returned_from_api(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels = AsyncMock(return_value=[])
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    
    count, error = await index_slack_messages(mock_session, 1, 1)
    assert count == 0
    assert error == "No channels to index after filtering." # This is the specific message when no channels are left
    # Verify last_indexed_at is updated because the task "ran" successfully even if no channels
    assert base_slack_connector.last_indexed_at is not None 

@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_all_member_channels_filter(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.return_value = [
        {"id": "C1", "name": "Channel1", "is_member": True, "is_private": False},
        {"id": "C2", "name": "Channel2", "is_member": True, "is_private": False}, # Bot is member
    ]
    mock_slack_history_instance.get_conversation_history.return_value = [
        {"ts": "1", "user": "U1", "text": "msg1"},
    ]
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    base_slack_connector.config["slack_membership_filter_type"] = "all_member_channels"

    count, _ = await index_slack_messages(mock_session, 1, 1)
    assert count == 2 # Two documents created, one for each channel
    assert mock_slack_history_instance.get_conversation_history.call_count == 2
    mock_slack_history_instance.get_conversation_history.assert_any_call(channel_id="C1", limit=100, oldest=mock_slack_history_instance.convert_date_to_timestamp.return_value, latest=mock_slack_history_instance.convert_date_to_timestamp.return_value)
    mock_slack_history_instance.get_conversation_history.assert_any_call(channel_id="C2", limit=100, oldest=mock_slack_history_instance.convert_date_to_timestamp.return_value, latest=mock_slack_history_instance.convert_date_to_timestamp.return_value)


@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_selected_member_channels_filter(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.return_value = [
        {"id": "C1", "name": "Channel1", "is_member": True, "is_private": False},
        {"id": "C2", "name": "Channel2", "is_member": True, "is_private": False},
        {"id": "C3", "name": "Channel3", "is_member": True, "is_private": False},
    ]
    mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1", "user": "U1", "text": "msg1"}]
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    base_slack_connector.config["slack_membership_filter_type"] = "selected_member_channels"
    base_slack_connector.config["slack_selected_channel_ids"] = ["C1", "C3"]

    count, _ = await index_slack_messages(mock_session, 1, 1)
    assert count == 2
    assert mock_slack_history_instance.get_conversation_history.call_count == 2
    mock_slack_history_instance.get_conversation_history.assert_any_call(channel_id="C1", limit=100, oldest=mock_slack_history_instance.convert_date_to_timestamp.return_value, latest=mock_slack_history_instance.convert_date_to_timestamp.return_value)
    mock_slack_history_instance.get_conversation_history.assert_any_call(channel_id="C3", limit=100, oldest=mock_slack_history_instance.convert_date_to_timestamp.return_value, latest=mock_slack_history_instance.convert_date_to_timestamp.return_value)
    # C2 should not have been called


@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_target_channel_ids_interaction(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.return_value = [
        {"id": "C1", "name": "Channel1", "is_member": True, "is_private": False},
        {"id": "C2", "name": "Channel2", "is_member": True, "is_private": False}, # Configured but not targeted
        {"id": "C3", "name": "Channel3", "is_member": True, "is_private": False}, # Targeted
    ]
    mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1", "user": "U1", "text": "msg1"}]
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    base_slack_connector.config["slack_membership_filter_type"] = "all_member_channels" # All are initially valid

    count, _ = await index_slack_messages(mock_session, 1, 1, target_channel_ids=["C1", "C3"])
    assert count == 2 # Only C1 and C3
    mock_slack_history_instance.get_conversation_history.assert_any_call(channel_id="C1", limit=base_slack_connector.config["slack_max_messages_per_channel_periodic"], oldest=mock_slack_history_instance.convert_date_to_timestamp.return_value, latest=mock_slack_history_instance.convert_date_to_timestamp.return_value)
    mock_slack_history_instance.get_conversation_history.assert_any_call(channel_id="C3", limit=base_slack_connector.config["slack_max_messages_per_channel_periodic"], oldest=mock_slack_history_instance.convert_date_to_timestamp.return_value, latest=mock_slack_history_instance.convert_date_to_timestamp.return_value)
    # Ensure C2 was not called for history
    calls = mock_slack_history_instance.get_conversation_history.call_args_list
    for c in calls:
        assert c.kwargs['channel_id'] != "C2"

@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_initial_indexing_days_logic(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    base_slack_connector.last_indexed_at = None # Ensure initial run
    base_slack_connector.config["slack_initial_indexing_days"] = 7
    
    # Mock convert_date_to_timestamp to check its input
    mock_converter = MagicMock()
    # Make it return a fixed value so we can check the call to get_conversation_history
    fixed_ts = str(int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp()))
    mock_converter.return_value = fixed_ts 
    # Patch the static method on the class, not the instance
    with patch.object(SlackHistory, 'convert_date_to_timestamp', mock_converter):
        mock_slack_history_instance.get_all_channels.return_value = [{"id": "C1", "name": "Chan1", "is_member": True}]
        mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1"}]
        MockSlackHistory.return_value = mock_slack_history_instance
        mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector

        await index_slack_messages(mock_session, 1, 1)
        
        # Check if convert_date_to_timestamp was called correctly for the start date
        # It's called internally for both oldest and latest. We are interested in the 'oldest' logic.
        # The actual call to SlackHistory.convert_date_to_timestamp for 'oldest' happens inside index_slack_messages.
        # We can assert that get_conversation_history was called with the 'fixed_ts'
        
        latest_ts_for_call = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))

        mock_slack_history_instance.get_conversation_history.assert_called_once_with(
            channel_id="C1",
            limit=base_slack_connector.config["slack_initial_max_messages_per_channel"],
            oldest=fixed_ts, # This is the key check
            latest=latest_ts_for_call
        )

@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_initial_indexing_all_time(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    base_slack_connector.last_indexed_at = None
    base_slack_connector.config["slack_initial_indexing_days"] = -1
    mock_slack_history_instance.get_all_channels.return_value = [{"id": "C1", "name": "Chan1", "is_member": True}]
    mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1"}]
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector

    await index_slack_messages(mock_session, 1, 1)
    latest_ts_for_call = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
    mock_slack_history_instance.get_conversation_history.assert_called_once_with(
        channel_id="C1",
        limit=base_slack_connector.config["slack_initial_max_messages_per_channel"],
        oldest="0", # All time
        latest=latest_ts_for_call
    )


@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_periodic_indexing_logic(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    last_indexed_time = datetime.now(timezone.utc) - timedelta(days=5)
    base_slack_connector.last_indexed_at = last_indexed_time
    
    mock_slack_history_instance.get_all_channels.return_value = [{"id": "C1", "name": "Chan1", "is_member": True}]
    mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1"}]
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector

    await index_slack_messages(mock_session, 1, 1)
    
    expected_oldest_ts = str(int(last_indexed_time.timestamp()))
    latest_ts_for_call = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))

    mock_slack_history_instance.get_conversation_history.assert_called_once_with(
        channel_id="C1",
        limit=base_slack_connector.config["slack_max_messages_per_channel_periodic"],
        oldest=expected_oldest_ts,
        latest=latest_ts_for_call
    )

@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_reindex_force_all_with_dates(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.return_value = [{"id": "C1", "name": "Chan1", "is_member": True}]
    mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1"}]
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector

    start_date_str = "2023-03-01"
    latest_date_str = "2023-03-10"
    expected_oldest = SlackHistory.convert_date_to_timestamp(start_date_str)
    expected_latest = SlackHistory.convert_date_to_timestamp(latest_date_str, is_latest=True)

    await index_slack_messages(mock_session, 1, 1, 
                               target_channel_ids=["C1"], 
                               force_reindex_all_messages=True, 
                               reindex_start_date_str=start_date_str, 
                               reindex_latest_date_str=latest_date_str)
    
    mock_slack_history_instance.get_conversation_history.assert_called_once_with(
        channel_id="C1",
        limit=base_slack_connector.config["slack_initial_max_messages_per_channel"], # Uses initial limit
        oldest=expected_oldest,
        latest=expected_latest
    )

@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_document_creation(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.return_value = [{"id": "C1", "name": "TestChannel", "is_member": True}]
    mock_slack_history_instance.get_conversation_history.return_value = [
        {"ts": "1", "user": "U1", "text": "Hello"},
        {"ts": "2", "user": "U2", "text": "World", "subtype": "bot_message"}, # Should be skipped
    ]
    # Configure format_message to return what's needed by the task
    mock_slack_history_instance.format_message.side_effect = lambda msg, include_user_info=False: {
        "user_id": msg["user"], "text": msg["text"], "datetime": "time", "subtype": msg.get("subtype")
    }

    MockSlackHistory.return_value = mock_slack_history_instance
    # Simulate no existing document for this channel
    mock_session.execute.return_value.scalars.return_value.all.return_value = [] 
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector # For connector fetch

    count, _ = await index_slack_messages(mock_session, 1, 1)
    assert count == 1
    
    # Check Document creation (session.add was called with a Document instance)
    added_object = mock_session.add.call_args[0][0]
    assert isinstance(added_object, Document)
    assert added_object.title == "Slack - TestChannel"
    assert added_object.document_type == DocumentType.SLACK_CONNECTOR
    assert added_object.document_metadata["channel_id"] == "C1"
    assert added_object.document_metadata["message_count"] == 1 # Only one valid message
    assert added_object.content == "Test Summary" # From mock_app_config
    assert len(added_object.chunks) == 2 # From mock_app_config chunker

    # Check that bot message was skipped via format_message calls
    format_calls = mock_slack_history_instance.format_message.call_args_list
    assert len(format_calls) == 1 # Only called for the non-bot message
    assert format_calls[0].args[0]['text'] == "Hello"
    
    assert mock_session.commit.call_count == 1


@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_document_update(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.return_value = [{"id": "C1", "name": "TestChannel", "is_member": True}]
    mock_slack_history_instance.get_conversation_history.return_value = [{"ts": "1", "user": "U1", "text": "Updated Content"}]
    mock_slack_history_instance.format_message.return_value = {"user_id": "U1", "text": "Updated Content", "datetime":"time"}
    MockSlackHistory.return_value = mock_slack_history_instance
    
    existing_doc = Document(id=101, search_space_id=1, title="Old Title", document_type=DocumentType.SLACK_CONNECTOR, document_metadata={"channel_id": "C1"})
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
    # Simulate existing document for this channel_id
    mock_session.execute.return_value.scalars.return_value.all.return_value = [existing_doc] 

    count, _ = await index_slack_messages(mock_session, 1, 1)
    assert count == 1 # 0 new, 1 updated
    
    assert existing_doc.content == "Test Summary" # Updated content from summary
    assert existing_doc.document_metadata["message_count"] == 1
    # Check that session.delete was called for old chunks (implicitly via relationship or explicit call)
    # This depends on ORM setup or if task explicitly deletes.
    # For this test, we assume the task handles deleting old chunks if needed.
    # The provided task code does execute a delete statement for chunks.
    delete_chunk_call = None
    for call_item in mock_session.execute.call_args_list:
        if "DELETE" in str(call_item.args[0]): # Check if a DELETE statement was executed
            delete_chunk_call = call_item
            break
    assert delete_chunk_call is not None 
    
    # Verify new chunks are added
    num_new_chunks_added = 0
    for call_item in mock_session.add.call_args_list:
        if isinstance(call_item.args[0], Chunk):
            num_new_chunks_added +=1
            assert call_item.args[0].document_id == existing_doc.id # Associated with existing doc
    assert num_new_chunks_added == 2 # From mock_app_config chunker

    assert mock_session.commit.call_count == 1

@pytest.mark.asyncio
async def test_last_indexed_at_update_logic(mock_session, base_slack_connector):
    # Scenario 1: update_last_indexed = True, documents processed
    mock_slack_history_instance_s1 = MagicMock(spec=SlackHistory)
    mock_slack_history_instance_s1.get_all_channels = AsyncMock(return_value=[{"id": "C1", "name": "Chan1", "is_member": True}])
    mock_slack_history_instance_s1.get_conversation_history = AsyncMock(return_value=[{"ts": "1", "user": "U1", "text": "msg"}])
    mock_slack_history_instance_s1.format_message = MagicMock(return_value={"user_id":"U1", "text":"msg", "datetime":"t"})

    with patch('app.tasks.connectors_indexing_tasks.SlackHistory', return_value=mock_slack_history_instance_s1):
        mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
        base_slack_connector.last_indexed_at = None # Reset for this test part
        await index_slack_messages(mock_session, 1, 1, update_last_indexed=True)
        assert base_slack_connector.last_indexed_at is not None
        original_last_indexed_at = base_slack_connector.last_indexed_at

    # Scenario 2: update_last_indexed = False
    mock_slack_history_instance_s2 = MagicMock(spec=SlackHistory)
    mock_slack_history_instance_s2.get_all_channels = AsyncMock(return_value=[{"id": "C1", "name": "Chan1", "is_member": True}])
    mock_slack_history_instance_s2.get_conversation_history = AsyncMock(return_value=[{"ts": "1", "user": "U1", "text": "msg"}])
    mock_slack_history_instance_s2.format_message = MagicMock(return_value={"user_id":"U1", "text":"msg", "datetime":"t"})
    
    with patch('app.tasks.connectors_indexing_tasks.SlackHistory', return_value=mock_slack_history_instance_s2):
        mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector
        # last_indexed_at should remain as it was from scenario 1
        await index_slack_messages(mock_session, 1, 1, update_last_indexed=False)
        assert base_slack_connector.last_indexed_at == original_last_indexed_at


@pytest.mark.asyncio
@patch('app.tasks.connectors_indexing_tasks.SlackHistory')
async def test_error_get_all_channels_exception(MockSlackHistory, mock_session, base_slack_connector, mock_slack_history_instance):
    mock_slack_history_instance.get_all_channels.side_effect = Exception("Failed to get channels")
    MockSlackHistory.return_value = mock_slack_history_instance
    mock_session.execute.return_value.scalars.return_value.first.return_value = base_slack_connector

    count, error = await index_slack_messages(mock_session, 1, 1)
    assert count == 0
    assert "Failed to get Slack channels: Failed to get channels" in error
    assert mock_session.rollback.call_count == 1 # Should rollback on general exception

@pytest.mark.asyncio
async def test_db_error_on_commit(mock_session, base_slack_connector):
    # This test needs to allow the initial connector fetch to succeed, then fail on commit
    mock_connector_fetch_result = MagicMock()
    mock_connector_fetch_result.scalars.return_value.first.return_value = base_slack_connector
    
    mock_docs_fetch_result = MagicMock()
    mock_docs_fetch_result.scalars.return_value.all.return_value = [] # No existing docs

    # Configure side_effect for session.execute
    mock_session.execute.side_effect = [
        mock_connector_fetch_result, # First call for getting connector
        mock_docs_fetch_result       # Second call for getting existing_docs
    ]
    
    mock_session.commit.side_effect = SQLAlchemyError("DB Commit Failed")

    mock_slack_history_instance_db_error = MagicMock(spec=SlackHistory)
    mock_slack_history_instance_db_error.get_all_channels = AsyncMock(return_value=[{"id": "C1", "name": "Chan1", "is_member": True}])
    mock_slack_history_instance_db_error.get_conversation_history = AsyncMock(return_value=[{"ts": "1", "user":"U1", "text":"msg"}])
    mock_slack_history_instance_db_error.format_message = MagicMock(return_value={"user_id":"U1", "text":"msg", "datetime":"t"})

    with patch('app.tasks.connectors_indexing_tasks.SlackHistory', return_value=mock_slack_history_instance_db_error):
        count, error = await index_slack_messages(mock_session, 1, 1)
        assert count == 0
        assert "Database error: DB Commit Failed" in error
        assert mock_session.rollback.call_count == 1 # Ensure rollback on SQLAlchemyError
