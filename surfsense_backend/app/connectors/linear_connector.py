"""
Linear Connector Module

A module for retrieving issues and comments from Linear.
Allows fetching issue lists and their comments with date range filtering.
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union


class LinearConnector:
    """Class for retrieving issues and comments from Linear."""
    
    def __init__(self, token: str = None):
        """
        Initialize the LinearConnector class.
        
        Args:
            token: Linear API token (optional, can be set later with set_token)
        """
        self.token = token
        self.api_url = "https://api.linear.app/graphql"
    
    def set_token(self, token: str) -> None:
        """
        Set the Linear API token.
        
        Args:
            token: Linear API token
        """
        self.token = token
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get headers for Linear API requests.
        
        Returns:
            Dictionary of headers
            
        Raises:
            ValueError: If no Linear token has been set
        """
        if not self.token:
            raise ValueError("Linear token not initialized. Call set_token() first.")
            
        return {
            'Content-Type': 'application/json',
            'Authorization': self.token
        }
    
    def execute_graphql_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the Linear API.
        
        Args:
            query: GraphQL query string
            variables: Variables for the GraphQL query (optional)
            
        Returns:
            Response data from the API
            
        Raises:
            ValueError: If no Linear token has been set
            Exception: If the API request fails
        """
        if not self.token:
            raise ValueError("Linear token not initialized. Call set_token() first.")
            
        headers = self.get_headers()
        payload = {'query': query}
        
        if variables:
            payload['variables'] = variables
            
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Query failed with status code {response.status_code}: {response.text}")
    
    def get_all_issues(self, include_comments: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all issues from Linear.
        
        Args:
            include_comments: Whether to include comments in the response
            
        Returns:
            List of issue objects
            
        Raises:
            ValueError: If no Linear token has been set
            Exception: If the API request fails
        """
        comments_query = ""
        if include_comments:
            comments_query = """
            comments {
                nodes {
                    id
                    body
                    user {
                        id
                        name
                        email
                    }
                    createdAt
                    updatedAt
                }
            }
            """
            
        query = f"""
        query {{
            issues {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    state {{
                        id
                        name
                        type
                    }}
                    assignee {{
                        id
                        name
                        email
                    }}
                    creator {{
                        id
                        name
                        email
                    }}
                    createdAt
                    updatedAt
                    {comments_query}
                }}
            }}
        }}
        """
        
        result = self.execute_graphql_query(query)
        
        # Extract issues from the response
        if "data" in result and "issues" in result["data"] and "nodes" in result["data"]["issues"]:
            return result["data"]["issues"]["nodes"]
        
        return []
    
    def get_issues_by_date_range(
        self, 
        start_date: str, 
        end_date: str,
        include_comments: bool = True
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch issues within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            include_comments: Whether to include comments in the response
            
        Returns:
            Tuple containing (issues list, error message or None)
        """
        # Convert date strings to ISO format
        try:
            # For Linear API: we need to use a more specific format for the filter
            # Instead of DateTime, use a string in the filter for DateTimeOrDuration
            comments_query = ""
            if include_comments:
                comments_query = """
                comments {
                    nodes {
                        id
                        body
                        user {
                            id
                            name
                            email
                        }
                        createdAt
                        updatedAt
                    }
                }
                """
                
            # Query issues that were either created OR updated within the date range
            # This ensures we catch both new issues and updated existing issues
            query = f"""
            query IssuesByDateRange($after: String) {{
                issues(
                    first: 100,
                    after: $after,
                    filter: {{
                        or: [
                            {{
                                createdAt: {{
                                    gte: "{start_date}T00:00:00Z"
                                    lte: "{end_date}T23:59:59Z"
                                }}
                            }},
                            {{
                                updatedAt: {{
                                    gte: "{start_date}T00:00:00Z"
                                    lte: "{end_date}T23:59:59Z"
                                }}
                            }}
                        ]
                    }}
                ) {{
                    nodes {{
                        id
                        identifier
                        title
                        description
                        state {{
                            id
                            name
                            type
                        }}
                        assignee {{
                            id
                            name
                            email
                        }}
                        creator {{
                            id
                            name
                            email
                        }}
                        createdAt
                        updatedAt
                        {comments_query}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
            """
            
            try:
                all_issues = []
                has_next_page = True
                cursor = None
                
                # Handle pagination to get all issues
                while has_next_page:
                    variables = {"after": cursor} if cursor else {}
                    result = self.execute_graphql_query(query, variables)
                    
                    # Check for errors
                    if "errors" in result:
                        error_message = "; ".join([error.get("message", "Unknown error") for error in result["errors"]])
                        return [], f"GraphQL errors: {error_message}"
                    
                    # Extract issues from the response
                    if "data" in result and "issues" in result["data"]:
                        issues_page = result["data"]["issues"]
                        
                        # Add issues from this page
                        if "nodes" in issues_page:
                            all_issues.extend(issues_page["nodes"])
                        
                        # Check if there are more pages
                        if "pageInfo" in issues_page:
                            page_info = issues_page["pageInfo"]
                            has_next_page = page_info.get("hasNextPage", False)
                            cursor = page_info.get("endCursor") if has_next_page else None
                        else:
                            has_next_page = False
                    else:
                        has_next_page = False
                
                if not all_issues:
                    return [], "No issues found in the specified date range."
                
                return all_issues, None
                
            except Exception as e:
                return [], f"Error fetching issues: {str(e)}"
                
        except ValueError as e:
            return [], f"Invalid date format: {str(e)}. Please use YYYY-MM-DD."
    
    def format_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format an issue for easier consumption.
        
        Args:
            issue: The issue object from Linear API
            
        Returns:
            Formatted issue dictionary
        """
        # Extract basic issue details
        formatted = {
            "id": issue.get("id", ""),
            "identifier": issue.get("identifier", ""),
            "title": issue.get("title", ""),
            "description": issue.get("description", ""),
            "state": issue.get("state", {}).get("name", "Unknown") if issue.get("state") else "Unknown",
            "state_type": issue.get("state", {}).get("type", "Unknown") if issue.get("state") else "Unknown",
            "created_at": issue.get("createdAt", ""),
            "updated_at": issue.get("updatedAt", ""),
            "creator": {
                "id": issue.get("creator", {}).get("id", "") if issue.get("creator") else "",
                "name": issue.get("creator", {}).get("name", "Unknown") if issue.get("creator") else "Unknown",
                "email": issue.get("creator", {}).get("email", "") if issue.get("creator") else ""
            } if issue.get("creator") else {"id": "", "name": "Unknown", "email": ""},
            "assignee": {
                "id": issue.get("assignee", {}).get("id", ""),
                "name": issue.get("assignee", {}).get("name", "Unknown"),
                "email": issue.get("assignee", {}).get("email", "")
            } if issue.get("assignee") else None,
            "comments": []
        }
        
        # Extract comments if available
        if "comments" in issue and "nodes" in issue["comments"]:
            for comment in issue["comments"]["nodes"]:
                formatted_comment = {
                    "id": comment.get("id", ""),
                    "body": comment.get("body", ""),
                    "created_at": comment.get("createdAt", ""),
                    "updated_at": comment.get("updatedAt", ""),
                    "user": {
                        "id": comment.get("user", {}).get("id", "") if comment.get("user") else "",
                        "name": comment.get("user", {}).get("name", "Unknown") if comment.get("user") else "Unknown",
                        "email": comment.get("user", {}).get("email", "") if comment.get("user") else ""
                    } if comment.get("user") else {"id": "", "name": "Unknown", "email": ""}
                }
                formatted["comments"].append(formatted_comment)
        
        return formatted
    
    def format_issue_to_markdown(self, issue: Dict[str, Any]) -> str:
        """
        Convert an issue to markdown format.
        
        Args:
            issue: The issue object (either raw or formatted)
            
        Returns:
            Markdown string representation of the issue
        """
        # Format the issue if it's not already formatted
        if "identifier" not in issue:
            issue = self.format_issue(issue)
        
        # Build the markdown content
        markdown = f"# {issue.get('identifier', 'No ID')}: {issue.get('title', 'No Title')}\n\n"
        
        if issue.get('state'):
            markdown += f"**Status:** {issue['state']}\n\n"
        
        if issue.get('assignee') and issue['assignee'].get('name'):
            markdown += f"**Assignee:** {issue['assignee']['name']}\n"
        
        if issue.get('creator') and issue['creator'].get('name'):
            markdown += f"**Created by:** {issue['creator']['name']}\n"
        
        if issue.get('created_at'):
            created_date = self.format_date(issue['created_at'])
            markdown += f"**Created:** {created_date}\n"
        
        if issue.get('updated_at'):
            updated_date = self.format_date(issue['updated_at'])
            markdown += f"**Updated:** {updated_date}\n\n"
        
        if issue.get('description'):
            markdown += f"## Description\n\n{issue['description']}\n\n"
        
        if issue.get('comments'):
            markdown += f"## Comments ({len(issue['comments'])})\n\n"
            
            for comment in issue['comments']:
                user_name = "Unknown"
                if comment.get('user') and comment['user'].get('name'):
                    user_name = comment['user']['name']
                
                comment_date = "Unknown date"
                if comment.get('created_at'):
                    comment_date = self.format_date(comment['created_at'])
                
                markdown += f"### {user_name} ({comment_date})\n\n{comment.get('body', '')}\n\n---\n\n"
        
        return markdown
    
    @staticmethod
    def format_date(iso_date: str) -> str:
        """
        Format an ISO date string to a more readable format.
        
        Args:
            iso_date: ISO format date string
            
        Returns:
            Formatted date string
        """
        if not iso_date or not isinstance(iso_date, str):
            return "Unknown date"
            
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return iso_date


# Example usage (uncomment to use):
"""
if __name__ == "__main__":
    # Set your token here
    token = "YOUR_LINEAR_API_KEY"
    
    linear = LinearConnector(token)
    
    try:
        # Get all issues with comments
        issues = linear.get_all_issues()
        print(f"Retrieved {len(issues)} issues")
        
        # Format and print the first issue as markdown
        if issues:
            issue_md = linear.format_issue_to_markdown(issues[0])
            print("\nSample Issue in Markdown:\n")
            print(issue_md)
            
        # Get issues by date range
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        date_issues, error = linear.get_issues_by_date_range(start_date, end_date)
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"\nRetrieved {len(date_issues)} issues from {start_date} to {end_date}")
    
    except Exception as e:
        print(f"Error: {e}")
"""
