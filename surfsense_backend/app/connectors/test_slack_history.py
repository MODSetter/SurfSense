import unittest
import time # Imported to be available for patching target module
from unittest.mock import patch, Mock, call
from slack_sdk.errors import SlackApiError

# Since test_slack_history.py is in the same directory as slack_history.py
from .slack_history import SlackHistory

class TestSlackHistoryGetAllChannels(unittest.TestCase):

    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient') # Patches where WebClient is looked up when SlackHistory instantiates it
    def test_get_all_channels_pagination_with_delay(self, MockWebClient, mock_sleep):
        mock_client_instance = MockWebClient.return_value
        
        page1_response = {
            "channels": [{"name": "general", "id": "C1"}, {"name": "dev", "id": "C0"}], # Added one more channel
            "response_metadata": {"next_cursor": "cursor123"}
        }
        page2_response = {
            "channels": [{"name": "random", "id": "C2"}],
            "response_metadata": {"next_cursor": ""} 
        }
        
        mock_client_instance.conversations_list.side_effect = [
            page1_response,
            page2_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels = slack_history.get_all_channels(include_private=True) # Explicitly True
        
        self.assertEqual(len(channels), 3) # Adjusted for 3 channels
        self.assertEqual(channels["general"], "C1")
        self.assertEqual(channels["dev"], "C0")
        self.assertEqual(channels["random"], "C2")
        
        expected_calls = [
            call(types="public_channel,private_channel", cursor=None, limit=1000),
            call(types="public_channel,private_channel", cursor="cursor123", limit=1000)
        ]
        mock_client_instance.conversations_list.assert_has_calls(expected_calls)
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)
        
        mock_sleep.assert_called_once_with(3)

    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_rate_limit_with_retry_after(self, MockWebClient, mock_sleep):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': '5'}
        
        successful_response = {
            "channels": [{"name": "general", "id": "C1"}],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            successful_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels = slack_history.get_all_channels(include_private=True)
        
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels["general"], "C1")
        mock_sleep.assert_called_once_with(5) 
        
        expected_calls = [
            call(types="public_channel,private_channel", cursor=None, limit=1000), # First attempt
            call(types="public_channel,private_channel", cursor=None, limit=1000)  # Retry attempt
        ]
        mock_client_instance.conversations_list.assert_has_calls(expected_calls)
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)

    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_rate_limit_no_retry_after_valid_header(self, MockWebClient, mock_sleep):
        # Test case for when Retry-After is not a digit
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': 'invalid_value'} # Non-digit value
        
        successful_response = {
            "channels": [{"name": "general", "id": "C1"}],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            successful_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels = slack_history.get_all_channels(include_private=True)
        
        self.assertEqual(channels["general"], "C1")
        mock_sleep.assert_called_once_with(60) # Default fallback
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)

    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_rate_limit_no_retry_after_header(self, MockWebClient, mock_sleep):
        # Test case for when Retry-After header is missing
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {} # No Retry-After header
        
        successful_response = {
            "channels": [{"name": "general", "id": "C1"}],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.side_effect = [
            SlackApiError(message="ratelimited", response=mock_error_response),
            successful_response
        ]
        
        slack_history = SlackHistory(token="fake_token")
        channels = slack_history.get_all_channels(include_private=True)
        
        self.assertEqual(channels["general"], "C1")
        mock_sleep.assert_called_once_with(60) # Default fallback
        self.assertEqual(mock_client_instance.conversations_list.call_count, 2)


    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_other_slack_api_error(self, MockWebClient, mock_sleep):
        mock_client_instance = MockWebClient.return_value
        
        mock_error_response = Mock()
        mock_error_response.status_code = 500 
        mock_error_response.headers = {}
        mock_error_response.data = {"ok": False, "error": "internal_error"} # Mocking response.data
        
        original_error = SlackApiError(message="server error", response=mock_error_response)
        mock_client_instance.conversations_list.side_effect = original_error
        
        slack_history = SlackHistory(token="fake_token")
        
        with self.assertRaises(SlackApiError) as context:
            slack_history.get_all_channels(include_private=True)
        
        # Check if the raised exception is the same one or has the same properties
        self.assertEqual(context.exception.response.status_code, 500)
        self.assertIn("server error", str(context.exception))
        mock_sleep.assert_not_called()
        mock_client_instance.conversations_list.assert_called_once_with(
            types="public_channel,private_channel", cursor=None, limit=1000
        )

    @patch('surfsense_backend.app.connectors.slack_history.time.sleep')
    @patch('slack_sdk.WebClient')
    def test_get_all_channels_handles_missing_name_id_gracefully(self, MockWebClient, mock_sleep):
        mock_client_instance = MockWebClient.return_value
        
        # Channel missing 'name', channel missing 'id', valid channel
        response_with_malformed_data = {
            "channels": [
                {"id": "C1_missing_name"}, 
                {"name": "channel_missing_id"},
                {"name": "general", "id": "C2_valid"}
            ],
            "response_metadata": {"next_cursor": ""}
        }
        
        mock_client_instance.conversations_list.return_value = response_with_malformed_data
        
        slack_history = SlackHistory(token="fake_token")
        # Patch print to check for warning messages
        with patch('builtins.print') as mock_print:
            channels = slack_history.get_all_channels(include_private=True)
        
        self.assertEqual(len(channels), 1) # Only the valid channel should be included
        self.assertIn("general", channels)
        self.assertEqual(channels["general"], "C2_valid")
        
        # Assert that warnings were printed for malformed channel data
        self.assertGreaterEqual(mock_print.call_count, 2) # At least two warnings
        mock_print.assert_any_call("Warning: Channel found with missing name or id. Data: {'id': 'C1_missing_name'}")
        mock_print.assert_any_call("Warning: Channel found with missing name or id. Data: {'name': 'channel_missing_id'}")

        mock_sleep.assert_not_called() # No pagination, so no sleep
        mock_client_instance.conversations_list.assert_called_once_with(
            types="public_channel,private_channel", cursor=None, limit=1000
        )

if __name__ == '__main__':
    unittest.main()
