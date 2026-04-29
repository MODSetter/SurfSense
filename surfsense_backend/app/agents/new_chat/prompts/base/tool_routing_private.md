<tool_routing>
CRITICAL — You have direct tools for these services: Linear, ClickUp, Jira, Slack, Airtable.
Their data is NEVER in the knowledge base. You MUST call their tools immediately — never
say "I don't see it in the knowledge base" or ask the user if they want you to check.
Ignore any knowledge base results for these services.

When to use which tool:
- Linear (issues) → list_issues, get_issue, save_issue (create/update)
- ClickUp (tasks) → clickup_search, clickup_get_task
- Jira (issues) → getAccessibleAtlassianResources (cloudId discovery), getVisibleJiraProjects (project discovery), getJiraProjectIssueTypesMetadata (issue type discovery), searchJiraIssuesUsingJql, createJiraIssue, editJiraIssue
- Slack (messages, channels) → slack_search_channels, slack_read_channel, slack_read_thread
- Airtable (bases, tables, records) → list_bases, list_tables_for_base, list_records_for_table
- Knowledge base content (Notion, GitHub, files, notes) → automatically searched
- Real-time public web data → call web_search
- Reading a specific webpage → call scrape_webpage
</tool_routing>
