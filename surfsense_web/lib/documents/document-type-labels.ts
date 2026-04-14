export function getDocumentTypeLabel(type: string): string {
	const labelMap: Record<string, string> = {
		EXTENSION: "Extension",
		CRAWLED_URL: "Web Page",
		FILE: "File",
		SLACK_CONNECTOR: "Slack",
		TEAMS_CONNECTOR: "Microsoft Teams",
		ONEDRIVE_FILE: "OneDrive",
		DROPBOX_FILE: "Dropbox",
		NOTION_CONNECTOR: "Notion",
		YOUTUBE_VIDEO: "YouTube Video",
		GITHUB_CONNECTOR: "GitHub",
		LINEAR_CONNECTOR: "Linear",
		DISCORD_CONNECTOR: "Discord",
		JIRA_CONNECTOR: "Jira",
		CONFLUENCE_CONNECTOR: "Confluence",
		CLICKUP_CONNECTOR: "ClickUp",
		GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		GOOGLE_GMAIL_CONNECTOR: "Gmail",
		GOOGLE_DRIVE_FILE: "Google Drive",
		AIRTABLE_CONNECTOR: "Airtable",
		LUMA_CONNECTOR: "Luma",
		ELASTICSEARCH_CONNECTOR: "Elasticsearch",
		BOOKSTACK_CONNECTOR: "BookStack",
		CIRCLEBACK: "Circleback",
		OBSIDIAN_CONNECTOR: "Obsidian",
		LOCAL_FOLDER_FILE: "Local Folder",
		SURFSENSE_DOCS: "SurfSense Docs",
		NOTE: "Note",
		COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Composio Google Drive",
		COMPOSIO_GMAIL_CONNECTOR: "Composio Gmail",
		COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Composio Google Calendar",
	};
	return (
		labelMap[type] ||
		type
			.split("_")
			.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
			.join(" ")
	);
}
