import unittest
from unittest.mock import Mock, patch

# Import the JiraConnector
from .jira_connector import JiraConnector


class TestJiraConnector(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.base_url = "https://test.atlassian.net"
        self.email = "test@example.com"
        self.api_token = "test_api_token"
        self.connector = JiraConnector(
            base_url=self.base_url, email=self.email, api_token=self.api_token
        )

    def test_init(self):
        """Test JiraConnector initialization."""
        self.assertEqual(self.connector.base_url, self.base_url)
        self.assertEqual(self.connector.email, self.email)
        self.assertEqual(self.connector.api_token, self.api_token)
        self.assertEqual(self.connector.api_version, "3")

    def test_init_with_trailing_slash(self):
        """Test JiraConnector initialization with trailing slash in URL."""
        connector = JiraConnector(
            base_url="https://test.atlassian.net/",
            email=self.email,
            api_token=self.api_token,
        )
        self.assertEqual(connector.base_url, "https://test.atlassian.net")

    def test_set_credentials(self):
        """Test setting credentials."""
        new_url = "https://newtest.atlassian.net/"
        new_email = "new@example.com"
        new_token = "new_api_token"

        self.connector.set_credentials(new_url, new_email, new_token)

        self.assertEqual(self.connector.base_url, "https://newtest.atlassian.net")
        self.assertEqual(self.connector.email, new_email)
        self.assertEqual(self.connector.api_token, new_token)

    def test_get_headers(self):
        """Test header generation."""
        headers = self.connector.get_headers()

        self.assertIn("Content-Type", headers)
        self.assertIn("Authorization", headers)
        self.assertIn("Accept", headers)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_get_headers_no_credentials(self):
        """Test header generation without credentials."""
        connector = JiraConnector()

        with self.assertRaises(ValueError) as context:
            connector.get_headers()

        self.assertIn("Jira credentials not initialized", str(context.exception))

    @patch("requests.get")
    def test_make_api_request_success(self, mock_get):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        result = self.connector.make_api_request("test/endpoint")

        self.assertEqual(result, {"test": "data"})
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_make_api_request_failure(self, mock_get):
        """Test failed API request."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        with self.assertRaises(Exception) as context:
            self.connector.make_api_request("test/endpoint")

        self.assertIn("API request failed with status code 401", str(context.exception))

    @patch.object(JiraConnector, "make_api_request")
    def test_get_all_projects(self, mock_api_request):
        """Test getting all projects."""
        mock_api_request.return_value = {
            "values": [
                {"id": "1", "key": "TEST", "name": "Test Project"},
                {"id": "2", "key": "DEMO", "name": "Demo Project"},
            ]
        }

        projects = self.connector.get_all_projects()

        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]["key"], "TEST")
        self.assertEqual(projects[1]["key"], "DEMO")
        mock_api_request.assert_called_once_with("project")

    @patch.object(JiraConnector, "make_api_request")
    def test_get_all_issues(self, mock_api_request):
        """Test getting all issues."""
        mock_api_request.return_value = {
            "issues": [
                {
                    "id": "1",
                    "key": "TEST-1",
                    "fields": {
                        "summary": "Test Issue",
                        "description": "Test Description",
                        "status": {"name": "Open"},
                        "priority": {"name": "High"},
                        "issuetype": {"name": "Bug"},
                        "project": {"key": "TEST"},
                        "created": "2023-01-01T10:00:00.000+0000",
                        "updated": "2023-01-01T12:00:00.000+0000",
                    },
                }
            ],
            "total": 1,
        }

        issues = self.connector.get_all_issues()

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["key"], "TEST-1")
        self.assertEqual(issues[0]["fields"]["summary"], "Test Issue")

    def test_format_issue(self):
        """Test issue formatting."""
        raw_issue = {
            "id": "1",
            "key": "TEST-1",
            "fields": {
                "summary": "Test Issue",
                "description": "Test Description",
                "status": {"name": "Open", "statusCategory": {"name": "To Do"}},
                "priority": {"name": "High"},
                "issuetype": {"name": "Bug"},
                "project": {"key": "TEST"},
                "created": "2023-01-01T10:00:00.000+0000",
                "updated": "2023-01-01T12:00:00.000+0000",
                "reporter": {
                    "accountId": "123",
                    "displayName": "John Doe",
                    "emailAddress": "john@example.com",
                },
                "assignee": {
                    "accountId": "456",
                    "displayName": "Jane Smith",
                    "emailAddress": "jane@example.com",
                },
            },
        }

        formatted = self.connector.format_issue(raw_issue)

        self.assertEqual(formatted["id"], "1")
        self.assertEqual(formatted["key"], "TEST-1")
        self.assertEqual(formatted["title"], "Test Issue")
        self.assertEqual(formatted["status"], "Open")
        self.assertEqual(formatted["priority"], "High")
        self.assertEqual(formatted["issue_type"], "Bug")
        self.assertEqual(formatted["project"], "TEST")
        self.assertEqual(formatted["reporter"]["display_name"], "John Doe")
        self.assertEqual(formatted["assignee"]["display_name"], "Jane Smith")

    def test_format_date(self):
        """Test date formatting."""
        iso_date = "2023-01-01T10:30:00.000+0000"
        formatted_date = JiraConnector.format_date(iso_date)

        self.assertEqual(formatted_date, "2023-01-01 10:30:00")

    def test_format_date_invalid(self):
        """Test date formatting with invalid input."""
        formatted_date = JiraConnector.format_date("invalid-date")
        self.assertEqual(formatted_date, "invalid-date")

        formatted_date = JiraConnector.format_date("")
        self.assertEqual(formatted_date, "Unknown date")

        formatted_date = JiraConnector.format_date(None)
        self.assertEqual(formatted_date, "Unknown date")

    def test_format_issue_to_markdown(self):
        """Test issue to markdown conversion."""
        formatted_issue = {
            "key": "TEST-1",
            "title": "Test Issue",
            "status": "Open",
            "priority": "High",
            "issue_type": "Bug",
            "project": "TEST",
            "assignee": {"display_name": "Jane Smith"},
            "reporter": {"display_name": "John Doe"},
            "created_at": "2023-01-01T10:00:00.000+0000",
            "updated_at": "2023-01-01T12:00:00.000+0000",
            "description": "Test Description",
            "comments": [],
        }

        markdown = self.connector.format_issue_to_markdown(formatted_issue)

        self.assertIn("# TEST-1: Test Issue", markdown)
        self.assertIn("**Status:** Open", markdown)
        self.assertIn("**Priority:** High", markdown)
        self.assertIn("**Type:** Bug", markdown)
        self.assertIn("**Project:** TEST", markdown)
        self.assertIn("**Assignee:** Jane Smith", markdown)
        self.assertIn("**Reporter:** John Doe", markdown)
        self.assertIn("## Description", markdown)
        self.assertIn("Test Description", markdown)


if __name__ == "__main__":
    unittest.main()
