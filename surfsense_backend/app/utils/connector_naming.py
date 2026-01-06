from app.db import SearchSourceConnectorType

# Friendly display names for connector types
BASE_NAME_FOR_TYPE = {
    SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR: "Gmail",
    SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR: "Google Drive",
    SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
    SearchSourceConnectorType.SLACK_CONNECTOR: "Slack",
    SearchSourceConnectorType.NOTION_CONNECTOR: "Notion",
    SearchSourceConnectorType.GITHUB_CONNECTOR: "GitHub",
    SearchSourceConnectorType.LINEAR_CONNECTOR: "Linear",
    SearchSourceConnectorType.JIRA_CONNECTOR: "Jira",
    SearchSourceConnectorType.DISCORD_CONNECTOR: "Discord",
    SearchSourceConnectorType.CONFLUENCE_CONNECTOR: "Confluence",
    SearchSourceConnectorType.AIRTABLE_CONNECTOR: "Airtable",
    SearchSourceConnectorType.LUMA_CONNECTOR: "Luma",
    # Add other connectors as needed, fallback below
}

def get_base_name_for_type(connector_type: SearchSourceConnectorType) -> str:
    return BASE_NAME_FOR_TYPE.get(connector_type, connector_type.replace("_", " ").title())


def generate_unique_connector_name(connector_type: SearchSourceConnectorType, identifier: str | None) -> str:
    base = get_base_name_for_type(connector_type)
    if identifier:
        return f"{base} - {identifier}"
    return base


def extract_identifier_from_credentials(connector_type: SearchSourceConnectorType, credentials: dict) -> str | None:
    if connector_type == SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR:
        return credentials.get("email") or credentials.get("user_email")
    if connector_type == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR:
        return credentials.get("email")
    if connector_type == SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR:
        return credentials.get("email")
    if connector_type == SearchSourceConnectorType.SLACK_CONNECTOR:
        return credentials.get("team_name") or credentials.get("team_id")
    if connector_type == SearchSourceConnectorType.NOTION_CONNECTOR:
        return credentials.get("workspace_name")
    if connector_type == SearchSourceConnectorType.GITHUB_CONNECTOR:
        return credentials.get("username")
    if connector_type == SearchSourceConnectorType.LINEAR_CONNECTOR:
        return credentials.get("workspace_name")
    if connector_type == SearchSourceConnectorType.JIRA_CONNECTOR:
        return credentials.get("base_url") or credentials.get("cloud_id")
    if connector_type == SearchSourceConnectorType.CONFLUENCE_CONNECTOR:
        return credentials.get("base_url") or credentials.get("cloud_id")
    if connector_type == SearchSourceConnectorType.DISCORD_CONNECTOR:
        return credentials.get("guild_name")
    if connector_type == SearchSourceConnectorType.AIRTABLE_CONNECTOR:
        return credentials.get("base_name")
    if connector_type == SearchSourceConnectorType.LUMA_CONNECTOR:
        return credentials.get("account_name")
    for key in ["email", "username", "workspace_name", "team_name", "base_url", "guild_name", "site_name", "account_name"]:
        if credentials.get(key):
            return credentials.get(key)
    return None

