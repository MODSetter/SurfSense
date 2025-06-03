import unittest
from unittest.mock import patch, Mock
from datetime import datetime

# Adjust the import path based on the actual location if test_github_connector.py
# is not in the same directory as github_connector.py or if paths are set up differently.
# Assuming surfsend_backend/app/connectors/test_github_connector.py
from surfsense_backend.app.connectors.github_connector import GitHubConnector
from github3.exceptions import ForbiddenError # Import the specific exception

class TestGitHubConnector(unittest.TestCase):

    @patch('surfsense_backend.app.connectors.github_connector.github_login')
    def test_get_user_repositories_uses_type_all(self, mock_github_login):
        # Mock the GitHub client object and its methods
        mock_gh_instance = Mock()
        mock_github_login.return_value = mock_gh_instance

        # Mock the self.gh.me() call in __init__ to prevent an actual API call
        mock_gh_instance.me.return_value = Mock() # Simple mock to pass initialization

        # Prepare mock repository data
        mock_repo1_data = Mock()
        mock_repo1_data.id = 1
        mock_repo1_data.name = "repo1"
        mock_repo1_data.full_name = "user/repo1"
        mock_repo1_data.private = False
        mock_repo1_data.html_url = "http://example.com/user/repo1"
        mock_repo1_data.description = "Test repo 1"
        mock_repo1_data.updated_at = datetime(2023, 1, 1, 10, 30, 0) # Added time component

        mock_repo2_data = Mock()
        mock_repo2_data.id = 2
        mock_repo2_data.name = "org-repo"
        mock_repo2_data.full_name = "org/org-repo"
        mock_repo2_data.private = True
        mock_repo2_data.html_url = "http://example.com/org/org-repo"
        mock_repo2_data.description = "Org repo"
        mock_repo2_data.updated_at = datetime(2023, 1, 2, 12, 0, 0) # Added time component
        
        # Configure the mock for gh.repositories() call
        # This method is an iterator, so it should return an iterable (e.g., a list)
        mock_gh_instance.repositories.return_value = [mock_repo1_data, mock_repo2_data]

        connector = GitHubConnector(token="fake_token")
        repositories = connector.get_user_repositories()

        # Assert that gh.repositories was called correctly
        mock_gh_instance.repositories.assert_called_once_with(type='all', sort='updated')

        # Assert the structure and content of the returned data
        expected_repositories = [
            {
                "id": 1, "name": "repo1", "full_name": "user/repo1", "private": False,
                "url": "http://example.com/user/repo1", "description": "Test repo 1",
                "last_updated": datetime(2023, 1, 1, 10, 30, 0)
            },
            {
                "id": 2, "name": "org-repo", "full_name": "org/org-repo", "private": True,
                "url": "http://example.com/org/org-repo", "description": "Org repo",
                "last_updated": datetime(2023, 1, 2, 12, 0, 0)
            }
        ]
        self.assertEqual(repositories, expected_repositories)
        self.assertEqual(len(repositories), 2)

    @patch('surfsense_backend.app.connectors.github_connector.github_login')
    def test_get_user_repositories_handles_empty_description_and_none_updated_at(self, mock_github_login):
        # Mock the GitHub client object and its methods
        mock_gh_instance = Mock()
        mock_github_login.return_value = mock_gh_instance
        mock_gh_instance.me.return_value = Mock()

        mock_repo_data = Mock()
        mock_repo_data.id = 1
        mock_repo_data.name = "repo_no_desc"
        mock_repo_data.full_name = "user/repo_no_desc"
        mock_repo_data.private = False
        mock_repo_data.html_url = "http://example.com/user/repo_no_desc"
        mock_repo_data.description = None # Test None description
        mock_repo_data.updated_at = None   # Test None updated_at

        mock_gh_instance.repositories.return_value = [mock_repo_data]
        connector = GitHubConnector(token="fake_token")
        repositories = connector.get_user_repositories()

        mock_gh_instance.repositories.assert_called_once_with(type='all', sort='updated')
        expected_repositories = [
            {
                "id": 1, "name": "repo_no_desc", "full_name": "user/repo_no_desc", "private": False,
                "url": "http://example.com/user/repo_no_desc", "description": "", # Expect empty string
                "last_updated": None # Expect None
            }
        ]
        self.assertEqual(repositories, expected_repositories)

    @patch('surfsense_backend.app.connectors.github_connector.github_login')
    def test_github_connector_initialization_failure_forbidden(self, mock_github_login):
        # Test that __init__ raises ValueError on auth failure (ForbiddenError)
        mock_gh_instance = Mock()
        mock_github_login.return_value = mock_gh_instance
        
        # Create a mock response object for the ForbiddenError
        # The actual response structure might vary, but github3.py's ForbiddenError
        # can be instantiated with just a response object that has a status_code.
        mock_response = Mock()
        mock_response.status_code = 403 # Typically Forbidden
        
        # Setup the side_effect for self.gh.me()
        mock_gh_instance.me.side_effect = ForbiddenError(mock_response)

        with self.assertRaises(ValueError) as context:
            GitHubConnector(token="invalid_token_forbidden")
        self.assertIn("Invalid GitHub token or insufficient permissions.", str(context.exception))

    @patch('surfsense_backend.app.connectors.github_connector.github_login')
    def test_github_connector_initialization_failure_authentication_failed(self, mock_github_login):
        # Test that __init__ raises ValueError on auth failure (AuthenticationFailed, which is a subclass of ForbiddenError)
        # For github3.py, AuthenticationFailed is more specific for token issues.
        from github3.exceptions import AuthenticationFailed

        mock_gh_instance = Mock()
        mock_github_login.return_value = mock_gh_instance
        
        mock_response = Mock()
        mock_response.status_code = 401 # Typically Unauthorized
        
        mock_gh_instance.me.side_effect = AuthenticationFailed(mock_response)

        with self.assertRaises(ValueError) as context:
            GitHubConnector(token="invalid_token_authfailed")
        self.assertIn("Invalid GitHub token or insufficient permissions.", str(context.exception))
    
    @patch('surfsense_backend.app.connectors.github_connector.github_login')
    def test_get_user_repositories_handles_api_exception(self, mock_github_login):
        mock_gh_instance = Mock()
        mock_github_login.return_value = mock_gh_instance
        mock_gh_instance.me.return_value = Mock()

        # Simulate an exception when calling repositories
        mock_gh_instance.repositories.side_effect = Exception("API Error")

        connector = GitHubConnector(token="fake_token")
        # We expect it to log an error and return an empty list
        with patch('surfsense_backend.app.connectors.github_connector.logger') as mock_logger:
            repositories = connector.get_user_repositories()
        
        self.assertEqual(repositories, [])
        mock_logger.error.assert_called_once()
        self.assertIn("Failed to fetch GitHub repositories: API Error", mock_logger.error.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
