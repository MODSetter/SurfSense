import unittest
from unittest.mock import patch, MagicMock, call
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timezone, timedelta

# Assuming SlackHistory is in app.connectors.slack_history
# Adjust the import path if your structure is different.
# For example, if 'app' is the root of your source:
from app.connectors.slack_history import SlackHistory 

class TestSlackHistory(unittest.TestCase):

    def setUp(self):
        self.dummy_token = "xoxb-test-token"
        # We patch WebClient in each test that needs it, so SlackHistory can be instantiated
        # without making actual API calls during setup.
        self.history = SlackHistory(token=self.dummy_token)


    @patch('app.connectors.slack_history.WebClient') # Patch where WebClient is looked up
    def test_init_and_set_token(self, MockWebClient):
        # Test __init__
        mock_client_instance = MockWebClient.return_value # Get the instance returned by MockWebClient()
        
        history_init = SlackHistory(token="test_init_token")
        MockWebClient.assert_called_once_with(token="test_init_token")
        self.assertEqual(history_init.client, mock_client_instance)

        # Reset mock for the next part of the test
        MockWebClient.reset_mock()

        # Test set_token
        history_set_token = SlackHistory() # Initialize without token first
        self.assertIsNone(history_set_token.client)
        
        history_set_token.set_token("test_set_token_token")
        MockWebClient.assert_called_once_with(token="test_set_token_token")
        self.assertEqual(history_set_token.client, mock_client_instance)


    @patch.object(WebClient, 'conversations_list')
    def test_get_all_channels_success_and_pagination(self, mock_conversations_list):
        # Simulate WebClient being already initialized in self.history
        self.history.client = mock_conversations_list.MagicMock() # Replace client with a mock that has conversations_list
        
        mock_response_page1 = MagicMock()
        mock_response_page1.data = {
            "channels": [
                {"id": "C1", "name": "general", "is_member": True, "is_private": False},
                {"id": "C2", "name": "random", "is_member": False, "is_private": False}, # is_member False
            ],
            "response_metadata": {"next_cursor": "cursor_page2"}
        }
        mock_response_page2 = MagicMock()
        mock_response_page2.data = {
            "channels": [
                {"id": "C3", "name": "private-project", "is_member": True, "is_private": True},
            ],
            "response_metadata": {"next_cursor": ""} 
        }
        self.history.client.conversations_list.side_effect = [mock_response_page1, mock_response_page2]

        channels = self.history.get_all_channels(include_private=True)
        
        self.assertEqual(len(channels), 3)
        self.assertEqual(channels[0]['id'], "C1")
        self.assertTrue(channels[0]['is_member']) # Verify is_member preserved
        self.assertEqual(channels[1]['id'], "C2")
        self.assertFalse(channels[1]['is_member']) # Verify is_member preserved
        self.assertEqual(channels[2]['id'], "C3")
        self.assertTrue(channels[2]['is_private'])

        expected_calls = [
            call(limit=200, cursor=None, types="public_channel,private_channel"),
            call(limit=200, cursor="cursor_page2", types="public_channel,private_channel")
        ]
        self.history.client.conversations_list.assert_has_calls(expected_calls)

    @patch.object(WebClient, 'conversations_list')
    def test_get_all_channels_public_only(self, mock_conversations_list):
        self.history.client = mock_conversations_list.MagicMock()
        mock_response = MagicMock()
        mock_response.data = {
            "channels": [{"id": "C1", "name": "general", "is_member": True, "is_private": False}],
            "response_metadata": {"next_cursor": ""}
        }
        self.history.client.conversations_list.return_value = mock_response

        self.history.get_all_channels(include_private=False)
        self.history.client.conversations_list.assert_called_once_with(limit=200, cursor=None, types="public_channel")

    @patch.object(WebClient, 'conversations_list')
    def test_get_all_channels_empty(self, mock_conversations_list):
        self.history.client = mock_conversations_list.MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"channels": [], "response_metadata": {"next_cursor": ""}}
        self.history.client.conversations_list.return_value = mock_response

        channels = self.history.get_all_channels()
        self.assertEqual(len(channels), 0)

    @patch.object(WebClient, 'conversations_list')
    def test_get_all_channels_api_error(self, mock_conversations_list):
        self.history.client = mock_conversations_list.MagicMock()
        # Simulate a SlackApiError
        self.history.client.conversations_list.side_effect = SlackApiError("API Error", MagicMock(data={"error": "test_error"}))
        
        with self.assertRaises(SlackApiError):
            self.history.get_all_channels()

    @patch.object(WebClient, 'conversations_history')
    def test_get_conversation_history_success_and_pagination(self, mock_conversations_history):
        self.history.client = mock_conversations_history.MagicMock()
        mock_response_page1 = MagicMock()
        mock_response_page1.data = {
            "messages": [{"ts": "123.001", "text": "Hello"}, {"ts": "123.002", "text": "World"}],
            "has_more": True,
            "response_metadata": {"next_cursor": "cursor_history2"}
        }
        mock_response_page2 = MagicMock()
        mock_response_page2.data = {
            "messages": [{"ts": "123.003", "text": "Again"}],
            "has_more": False
        }
        self.history.client.conversations_history.side_effect = [mock_response_page1, mock_response_page2]

        messages = self.history.get_conversation_history("C123", limit=3) # Request total 3 messages
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]['text'], "Hello")
        self.assertEqual(messages[2]['text'], "Again")

        # The internal page_limit in get_conversation_history is 100 (can be smaller than requested limit)
        expected_calls = [
            call(channel="C123", limit=3, oldest=None, latest=None, cursor=None), 
            call(channel="C123", limit=1, oldest=None, latest=None, cursor="cursor_history2") 
        ]
        self.history.client.conversations_history.assert_has_calls(expected_calls)


    @patch.object(WebClient, 'conversations_history')
    def test_get_conversation_history_with_timestamps(self, mock_conversations_history):
        self.history.client = mock_conversations_history.MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"messages": [{"ts": "1609500000.000", "text":"msg1"}], "has_more": False}
        self.history.client.conversations_history.return_value = mock_response

        oldest_ts_str = str(int(datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()))
        latest_ts_str = str(int(datetime(2021, 1, 2, 0, 0, 0, tzinfo=timezone.utc).timestamp()))


        self.history.get_conversation_history("C123", oldest=oldest_ts_str, latest=latest_ts_str, limit=50)
        self.history.client.conversations_history.assert_called_once_with(
            channel="C123", limit=50, oldest=oldest_ts_str, latest=latest_ts_str, cursor=None
        )

    @patch('logging.warning') # Patch logging where it's used (directly in slack_history module)
    @patch.object(WebClient, 'conversations_history')
    def test_get_conversation_history_not_in_channel(self, mock_conversations_history, mock_logging_warning):
        self.history.client = mock_conversations_history.MagicMock()
        error_response = MagicMock()
        error_response.data = {"ok": False, "error": "not_in_channel"}
        self.history.client.conversations_history.side_effect = SlackApiError("not_in_channel error", error_response)

        messages = self.history.get_conversation_history("C123")
        self.assertEqual(len(messages), 0) # Should return empty list
        mock_logging_warning.assert_called_once()
        self.assertIn("Bot is not in channel C123 or history is private.", mock_logging_warning.call_args[0][0])

    @patch.object(WebClient, 'conversations_history')
    def test_get_conversation_history_other_api_error(self, mock_conversations_history):
        self.history.client = mock_conversations_history.MagicMock()
        error_response = MagicMock()
        error_response.data = {"ok": False, "error": "some_other_error"}
        self.history.client.conversations_history.side_effect = SlackApiError("Some other error", error_response)

        with self.assertRaises(SlackApiError):
            self.history.get_conversation_history("C123")
            
    @patch.object(WebClient, 'conversations_history')
    def test_get_conversation_history_empty_messages_from_api(self, mock_conversations_history):
        self.history.client = mock_conversations_history.MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"messages": [], "has_more": False}
        self.history.client.conversations_history.return_value = mock_response

        messages = self.history.get_conversation_history("C123")
        self.assertEqual(len(messages), 0)

    def test_convert_date_to_timestamp_static(self):
        # Valid date
        ts = SlackHistory.convert_date_to_timestamp("2023-01-15")
        expected_dt = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(ts, str(int(expected_dt.timestamp())))

        # Valid date with is_latest = True
        ts_latest = SlackHistory.convert_date_to_timestamp("2023-01-15", is_latest=True)
        # Should be timestamp for 2023-01-16 00:00:00 UTC to include the whole day of 2023-01-15
        expected_dt_latest_inclusive = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc) + timedelta(days=1)
        self.assertEqual(ts_latest, str(int(expected_dt_latest_inclusive.timestamp())))
        
        # Invalid date format - Expect ValueError as per typical date parsing behavior
        with self.assertRaises(ValueError): 
            SlackHistory.convert_date_to_timestamp("15-01-2023")
        
        # Invalid date value
        with self.assertRaises(ValueError):
            SlackHistory.convert_date_to_timestamp("2023-13-01") # Month 13

    @patch.object(SlackHistory, 'get_conversation_history')
    def test_get_history_by_date_range_success(self, mock_get_conv_history):
        # Mock convert_date_to_timestamp if it's complex, or test its output directly.
        # Here, we assume convert_date_to_timestamp works as tested above.
        
        mock_get_conv_history.return_value = [{"text": "message from range"}]
        
        # Expected timestamps based on convert_date_to_timestamp logic
        start_date_str = "2023-01-10"
        end_date_str = "2023-01-12"
        
        expected_oldest_ts = str(int(datetime(2023, 1, 10, 0, 0, 0, tzinfo=timezone.utc).timestamp()))
        # For latest, it should be the start of the next day to include the entire end_date_str
        expected_latest_ts = str(int((datetime(2023, 1, 12, 0, 0, 0, tzinfo=timezone.utc) + timedelta(days=1)).timestamp()))

        messages, error = self.history.get_history_by_date_range("C123", start_date_str, end_date_str)
        
        self.assertIsNone(error)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['text'], "message from range")
        mock_get_conv_history.assert_called_once_with(
            channel_id="C123",
            oldest=expected_oldest_ts,
            latest=expected_latest_ts
        )

    def test_get_history_by_date_range_invalid_dates(self):
        # Test with invalid start_date format
        result, error = self.history.get_history_by_date_range("C123", "invalid-start-date", "2023-01-12")
        self.assertIsNone(result)
        self.assertIn("Invalid start_date format: invalid-start-date. Use YYYY-MM-DD.", error)

        # Test with invalid end_date format
        result, error = self.history.get_history_by_date_range("C123", "2023-01-10", "invalid-end-date")
        self.assertIsNone(result)
        self.assertIn("Invalid end_date format: invalid-end-date. Use YYYY-MM-DD.", error)

    @patch.object(WebClient, 'users_info')
    def test_get_user_info_success(self, mock_users_info):
        self.history.client = mock_users_info.MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"user": {"id": "U123", "name": "testuser", "real_name": "Test User"}}
        self.history.client.users_info.return_value = mock_response

        user_info = self.history.get_user_info("U123")
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info['name'], "testuser")
        self.history.client.users_info.assert_called_once_with(user="U123")

    @patch.object(WebClient, 'users_info')
    def test_get_user_info_api_error(self, mock_users_info):
        self.history.client = mock_users_info.MagicMock()
        self.history.client.users_info.side_effect = SlackApiError("API Error", MagicMock(data={"error": "user_not_found"}))
        
        user_info = self.history.get_user_info("U123") 
        self.assertIsNone(user_info) 

    def test_format_message_basic(self):
        raw_msg = {"type": "message", "user": "U123", "text": "Hello world", "ts": "1609459200.000100"} # 2021-01-01 00:00:00 UTC
        formatted = self.history.format_message(raw_msg)
        
        self.assertEqual(formatted['user_id'], "U123")
        self.assertEqual(formatted['text'], "Hello world")
        self.assertEqual(formatted['datetime'], "2021-01-01 00:00:00 UTC")
        self.assertNotIn('user_name', formatted) # Not requested

    @patch.object(SlackHistory, 'get_user_info')
    def test_format_message_with_user_info_and_real_name(self, mock_get_user_info):
        mock_get_user_info.return_value = {"real_name": "Test User Real", "name": "testusername"}
        raw_msg = {"type": "message", "user": "U123", "text": "Hello with user", "ts": "1609459200.000200"}
        
        formatted = self.history.format_message(raw_msg, include_user_info=True)
        
        mock_get_user_info.assert_called_once_with("U123")
        self.assertEqual(formatted['user_id'], "U123")
        self.assertEqual(formatted['user_name'], "Test User Real") # Prefers real_name
        self.assertEqual(formatted['text'], "Hello with user")

    @patch.object(SlackHistory, 'get_user_info')
    def test_format_message_with_user_info_name_fallback(self, mock_get_user_info):
        mock_get_user_info.return_value = {"name": "testusername_only"} # No real_name
        raw_msg = {"type": "message", "user": "U124", "text": "Name fallback", "ts": "1609459200.000300"}
        
        formatted = self.history.format_message(raw_msg, include_user_info=True)
        self.assertEqual(formatted['user_name'], "testusername_only")

    @patch.object(SlackHistory, 'get_user_info')
    def test_format_message_with_user_info_not_found(self, mock_get_user_info):
        mock_get_user_info.return_value = None # User info not found
        raw_msg = {"type": "message", "user": "U125", "text": "User not found", "ts": "1609459200.000350"}
        
        formatted = self.history.format_message(raw_msg, include_user_info=True)
        self.assertEqual(formatted['user_name'], "Unknown User")


    def test_format_message_with_files(self):
        raw_msg = {
            "type": "message", "user": "U123", "text": "Check attachments", "ts": "1609459200.000400",
            "files": [
                {"name": "file1.txt", "url_private_download": "http://example.com/file1.txt"},
                {"name": "image.png", "url_private_download": "http://example.com/image.png", "permalink": "http://slack.com/image.png"}
            ]
        }
        formatted = self.history.format_message(raw_msg)
        expected_text = (
            "Check attachments\n\n"
            "Attachments:\n"
            "- file1.txt (http://example.com/file1.txt)\n"
            "- image.png (http://slack.com/image.png)" # Prefers permalink
        )
        self.assertEqual(formatted['text'], expected_text)


    def test_format_message_with_thread_ts_and_replies(self):
        raw_msg = {
            "type": "message", "user": "U123", "text": "In a thread", "ts": "1609459200.000500",
            "thread_ts": "1609459100.000100", 
            "reply_count": 2 
        }
        formatted = self.history.format_message(raw_msg)
        self.assertEqual(formatted['text'], "In a thread (in reply to thread 1609459100.000100, 2 replies)")

    def test_format_message_subtype_handling(self):
        raw_msg = {"type": "message", "subtype": "channel_join", "user": "U123", "text": "U123 has joined the channel", "ts": "1609459200.000600"}
        formatted = self.history.format_message(raw_msg)
        self.assertIn("[channel_join message]", formatted['text']) # Check if subtype is mentioned

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
