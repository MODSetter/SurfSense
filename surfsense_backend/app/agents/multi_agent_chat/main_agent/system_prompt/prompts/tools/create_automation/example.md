<example>
user: "Every weekday at 9am, summarize new documents in folder 12 and post the summary to Slack channel #daily-digest."
→ create_automation(intent="Every weekday at 09:00 UTC, summarize documents added to folder_id=12 since the last run, then post the summary to Slack channel '#daily-digest'. Static inputs: folder_id=12, slack_channel='#daily-digest'.")
tool returns: {"status": "saved", "automation_id": 42, "name": "Daily folder 12 digest"}
(Reply briefly: "Saved as automation #42 — runs weekdays at 9am UTC.")
</example>

<example>
user: "Once a week on Mondays at 7am Paris time, draft a Notion page recapping last week's Jira tickets in project CORE."
→ create_automation(intent="Every Monday at 07:00 Europe/Paris, read last week's Jira issues in project CORE, then draft a Notion page recapping them. Static inputs: jira_project_key='CORE'. The user did NOT specify which Notion page the recap should sit under — leave notion_parent_page_id as a placeholder.")
tool returns: {"status": "saved", "automation_id": 51, "name": "Weekly CORE Jira recap"}
(Reply: "Saved as automation #51. I left the Notion parent page id as a placeholder — set it on the automation before next Monday.")
</example>
