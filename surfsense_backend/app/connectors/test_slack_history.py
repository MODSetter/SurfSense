import unittest
import time # Imported to be available for patching target module
from unittest.mock import patch, Mock, call
from slack_sdk.errors import SlackApiError

# Since test_slack_history.py is in the same directory as slack_history.py
from .slack_history import SlackHistory

class TestSlackHistoryGetAllChannels(unittest.TestCase):

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient') 
    def test_get_all_channels_pagination_with_delay(self, MockWebClient, mock_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        # Mock API responses now include is_private and is_member
        page1_response = {
            "channels": [
                {"name": "general", "id": "C1", "is_private": False, "is_member": True}, 
                {"name": "dev", "id": "C0", "is_private": False, "is_member": True}
            ],
            "response_metadata": {"next_cursor": "cursor123"}
        }
        page2_response = {
            "channels": [{"name": "random", "id": "C2", "is_private": True, "is_member": True}],
            "response_metadata": {"next_cursor": ""} 
        }
        
        mock_client_instance.conversations_list.side_effect = [
            page1_response,
            page2_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels_list = slack_history.get_all_channels(include_private=True)
        
        expected_channels_list = [
            {"id": "C1", "name": "general", "is_private": False, "is_member": True},
            {"id": "C0", "name": "dev", "is_private": False, "is_member": True},
            {"id": "C2", "name": "random", "is_private": True, "is_member": True}
        ]
        
        self.assertEqual(len(channels_list), 3)
        self.assertListEqual(channels_list, expected_channels_list) # Assert list equality
        
        expected_calls = [
            call(types="public_channel,private_channel", cursor=None, limit=1000),
            call(types="public_channel,private_channel", cursor="cursor123", limit=1000)
        ]
        mock_client_instance.conversations_list.assert_has_calls(expected_calls)
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)
        
        mock_sleep.assert_called_once_with(3)
        mock_logger.info.assert_called_once_with("Paginating for channels, waiting 3 seconds before next call. Cursor: cursor123")

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_rate_limit_with_retry_after(self, MockWebClient, mock_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': '5'}
        
        successful_response = {
            "channels": [{"name": "general", "id": "C1", "is_private": False, "is_member": True}],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            successful_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels_list = slack_history.get_all_channels(include_private=True)
        
        expected_channels_list = [{"id": "C1", "name": "general", "is_private": False, "is_member": True}]
        self.assertEqual(len(channels_list), 1)
        self.assertListEqual(channels_list, expected_channels_list)
        
        mock_sleep.assert_called_once_with(5) 
        mock_logger.warning.assert_called_once_with("Slack API rate limit hit while fetching channels. Waiting for 5 seconds. Cursor: None")
        
        expected_calls = [
            call(types="public_channel,private_channel", cursor=None, limit=1000), 
            call(types="public_channel,private_channel", cursor=None, limit=1000)
        ]
        mock_client_instance.conversations_list.assert_has_calls(expected_calls)
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_rate_limit_no_retry_after_valid_header(self, MockWebClient, mock_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': 'invalid_value'} 
        
        successful_response = {
            "channels": [{"name": "general", "id": "C1", "is_private": False, "is_member": True}],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            successful_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels_list = slack_history.get_all_channels(include_private=True)
        
        expected_channels_list = [{"id": "C1", "name": "general", "is_private": False, "is_member": True}]
        self.assertListEqual(channels_list, expected_channels_list)
        mock_sleep.assert_called_once_with(60) # Default fallback
        mock_logger.warning.assert_called_once_with("Slack API rate limit hit while fetching channels. Waiting for 60 seconds. Cursor: None")
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_rate_limit_no_retry_after_header(self, MockWebClient, mock_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {} 
        
        successful_response = {
            "channels": [{"name": "general", "id": "C1", "is_private": False, "is_member": True}],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            successful_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels_list = slack_history.get_all_channels(include_private=True)
        
        expected_channels_list = [{"id": "C1", "name": "general", "is_private": False, "is_member": True}]
        self.assertListEqual(channels_list, expected_channels_list)
        mock_sleep.assert_called_once_with(60) # Default fallback
        mock_logger.warning.assert_called_once_with("Slack API rate limit hit while fetching channels. Waiting for 60 seconds. Cursor: None")
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_other_slack_api_error(self, MockWebClient, mock_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 500 
        mock_error_response.headers = {}
        mock_error_response.data = {"ok": False, "error": "internal_error"} 
        
        original_error = SlackApiError(message="server error", response=mock_error_response)
        mock_client_instance.conversations_list.side_effect = original_error
        
        slack_history = SlackHistory(token="fake_token")
        
        with self.assertRaises(SlackApiError) as context:
            slack_history.get_all_channels(include_private=True)
        
        self.assertEqual(context.exception.response.status_code, 500)
        self.assertIn("server error", str(context.exception))
        mock_sleep.assert_not_called()
        mock_logger.warning.assert_not_called() # Ensure no rate limit log
        mock_client_instance.conversations_list.assert_called_once_with(
            types="public_channel,private_channel", cursor=None, limit=1000
        )

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_handles_missing_name_id_gracefully(self, MockWebClient, mock_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        response_with_malformed_data = {
            "channels": [
                {"id": "C1_missing_name", "is_private": False, "is_member": True}, 
                {"name": "channel_missing_id", "is_private": False, "is_member": True},
                {"name": "general", "id": "C2_valid", "is_private": False, "is_member": True}
            ],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.return_value = response_with_malformed_data
        
        slack_history = SlackHistory(token="fake_token")
        channels_list = slack_history.get_all_channels(include_private=True)
        
        expected_channels_list = [
            {"id": "C2_valid", "name": "general", "is_private": False, "is_member": True}
        ]
        self.assertEqual(len(channels_list), 1) 
        self.assertListEqual(channels_list, expected_channels_list)
        
        self.assertEqual(mock_logger.warning.call_count, 2)
        mock_logger.warning.assert_any_call("Channel found with missing name or id. Data: {'id': 'C1_missing_name', 'is_private': False, 'is_member': True}")
        mock_logger.warning.assert_any_call("Channel found with missing name or id. Data: {'name': 'channel_missing_id', 'is_private': False, 'is_member': True}")

        mock_sleep.assert_not_called() 
        mock_client_instance.conversations_list.assert_called_once_with(
            types="public_channel,private_channel", cursor=None, limit=1000
        )

if __name__ == '__main__':
    unittest.main()

class TestSlackHistoryGetConversationHistory(unittest.TestCase):

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_proactive_delay_single_page(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        mock_client_instance.conversations_history.return_value = {
            "messages": [{"text": "msg1"}],
            "has_more": False
        }
        
        slack_history = SlackHistory(token="fake_token")
        slack_history.get_conversation_history(channel_id="C123")
        
        mock_time_sleep.assert_called_once_with(1.2) # Proactive delay

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_proactive_delay_multiple_pages(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        mock_client_instance.conversations_history.side_effect = [
            {
                "messages": [{"text": "msg1"}],
                "has_more": True,
                "response_metadata": {"next_cursor": "cursor1"}
            },
            {
                "messages": [{"text": "msg2"}],
                "has_more": False
            }
        ]
        
        slack_history = SlackHistory(token="fake_token")
        slack_history.get_conversation_history(channel_id="C123")
        
        # Expected calls: 1.2 (page1), 1.2 (page2)
        self.assertEqual(mock_time_sleep.call_count, 2)
        mock_time_sleep.assert_has_calls([call(1.2), call(1.2)])

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_retry_after_logic(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': '5'}
        
        mock_client_instance.conversations_history.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            {"messages": [{"text": "msg1"}], "has_more": False}
        ]
        
        slack_history = SlackHistory(token="fake_token")
        messages = slack_history.get_conversation_history(channel_id="C123")
        
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["text"], "msg1")
        
        # Expected sleep calls: 1.2 (proactive for 1st attempt), 5 (rate limit), 1.2 (proactive for 2nd attempt)
        mock_time_sleep.assert_has_calls([call(1.2), call(5), call(1.2)], any_order=False)
        mock_logger.warning.assert_called_once() # Check that a warning was logged for rate limiting

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep') 
    @patch('slack_sdk.WebClient')
    def test_not_in_channel_error(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 403 # Typical for not_in_channel, but data matters more
        mock_error_response.data = {'ok': False, 'error': 'not_in_channel'}
        
        # This error is now raised by the inner try-except, then caught by the outer one
        mock_client_instance.conversations_history.side_effect = SlackApiError(
            message="not_in_channel error", 
            response=mock_error_response
        )
        
        slack_history = SlackHistory(token="fake_token")
        messages = slack_history.get_conversation_history(channel_id="C123")
        
        self.assertEqual(messages, [])
        mock_logger.warning.assert_called_with(
            "Bot is not in channel 'C123'. Cannot fetch history. Please add the bot to this channel."
        )
        mock_time_sleep.assert_called_once_with(1.2) # Proactive delay before the API call

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_other_slack_api_error_propagates(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 500
        mock_error_response.data = {'ok': False, 'error': 'internal_error'}
        original_error = SlackApiError(message="server error", response=mock_error_response)

        mock_client_instance.conversations_history.side_effect = original_error
        
        slack_history = SlackHistory(token="fake_token")
        
        with self.assertRaises(SlackApiError) as context:
            slack_history.get_conversation_history(channel_id="C123")
        
        self.assertIn("Error retrieving history for channel C123", str(context.exception))
        self.assertIs(context.exception.response, mock_error_response)
        mock_time_sleep.assert_called_once_with(1.2) # Proactive delay

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_general_exception_propagates(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        original_error = Exception("Something broke")
        mock_client_instance.conversations_history.side_effect = original_error
        
        slack_history = SlackHistory(token="fake_token")
        
        with self.assertRaises(Exception) as context: # Check for generic Exception
            slack_history.get_conversation_history(channel_id="C123")
        
        self.assertIs(context.exception, original_error) # Should re-raise the original error
        mock_logger.error.assert_called_once_with("Unexpected error in get_conversation_history for channel C123: Something broke")
        mock_time_sleep.assert_called_once_with(1.2) # Proactive delay

class TestSlackHistoryGetUserInfo(unittest.TestCase):

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_retry_after_logic(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': '3'} # Using 3 seconds for test
        
        successful_user_data = {"id": "U123", "name": "testuser"}
        
        mock_client_instance.users_info.side_effect = [
            SlackApiError(message="ratelimited_userinfo", response=mock_error_response),
            {"user": successful_user_data}
        ]
        
        slack_history = SlackHistory(token="fake_token")
        user_info = slack_history.get_user_info(user_id="U123")
        
        self.assertEqual(user_info, successful_user_data)
        
        # Assert that time.sleep was called for the rate limit
        mock_time_sleep.assert_called_once_with(3)
        mock_logger.warning.assert_called_once_with(
            "Rate limited by Slack on users.info for user U123. Retrying after 3 seconds."
        )
        # Assert users_info was called twice (original + retry)
        self.assertEqual(mock_client_instance.users_info.call_count, 2)
        mock_client_instance.users_info.assert_has_calls([call(user="U123"), call(user="U123")])

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep') # time.sleep might be called by other logic, but not expected here
    @patch('slack_sdk.WebClient')
    def test_other_slack_api_error_propagates(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 500 # Some other error
        mock_error_response.data = {'ok': False, 'error': 'internal_server_error'}
        original_error = SlackApiError(message="internal server error", response=mock_error_response)

        mock_client_instance.users_info.side_effect = original_error
        
        slack_history = SlackHistory(token="fake_token")
        
        with self.assertRaises(SlackApiError) as context:
            slack_history.get_user_info(user_id="U123")
        
        # Check that the raised error is the one we expect
        self.assertIn("Error retrieving user info for U123", str(context.exception))
        self.assertIs(context.exception.response, mock_error_response)
        mock_time_sleep.assert_not_called() # No rate limit sleep

    @patch('surfsense_backend.app.connectors.slack_history.logger')
    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_general_exception_propagates(self, MockWebClient, mock_time_sleep, mock_logger):
        mock_client_instance = MockWebClient.return_value
        original_error = Exception("A very generic problem")
        mock_client_instance.users_info.side_effect = original_error
        
        slack_history = SlackHistory(token="fake_token")
        
        with self.assertRaises(Exception) as context:
            slack_history.get_user_info(user_id="U123")
            
        self.assertIs(context.exception, original_error) # Check it's the exact same exception
        mock_logger.error.assert_called_once_with(
            "Unexpected error in get_user_info for user U123: A very generic problem"
        )
        mock_time_sleep.assert_not_called() # No rate limit sleep
