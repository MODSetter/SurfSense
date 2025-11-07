import { IconBrandWindows, IconBrandZoom } from "@tabler/icons-react";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { ConnectorCategory } from "./types";

export const connectorCategories: ConnectorCategory[] = [
	{
		id: "search-engines",
		title: "search_engines",
		connectors: [
			{
				id: "tavily-api",
				title: "Tavily API",
				description: "tavily_desc",
				icon: getConnectorIcon(EnumConnectorName.TAVILY_API, "h-6 w-6"),
				status: "available",
			},
			{
				id: "searxng",
				title: "SearxNG",
				description: "searxng_desc",
				icon: getConnectorIcon(EnumConnectorName.SEARXNG_API, "h-6 w-6"),
				status: "available",
			},
			{
				id: "linkup-api",
				title: "Linkup API",
				description: "linkup_desc",
				icon: getConnectorIcon(EnumConnectorName.LINKUP_API, "h-6 w-6"),
				status: "available",
			},
			{
				id: "elasticsearch-connector",
				title: "Elasticsearch",
				description: "elasticsearch_desc",
				icon: getConnectorIcon(EnumConnectorName.ELASTICSEARCH_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "baidu-search-api",
				title: "Baidu Search",
				description: "baidu_desc",
				icon: getConnectorIcon(EnumConnectorName.BAIDU_SEARCH_API, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "team-chats",
		title: "team_chats",
		connectors: [
			{
				id: "slack-connector",
				title: "Slack",
				description: "slack_desc",
				icon: getConnectorIcon(EnumConnectorName.SLACK_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "ms-teams",
				title: "Microsoft Teams",
				description: "teams_desc",
				icon: <IconBrandWindows className="h-6 w-6" />,
				status: "coming-soon",
			},
			{
				id: "discord-connector",
				title: "Discord",
				description: "discord_desc",
				icon: getConnectorIcon(EnumConnectorName.DISCORD_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "project-management",
		title: "project_management",
		connectors: [
			{
				id: "linear-connector",
				title: "Linear",
				description: "linear_desc",
				icon: getConnectorIcon(EnumConnectorName.LINEAR_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "jira-connector",
				title: "Jira",
				description: "jira_desc",
				icon: getConnectorIcon(EnumConnectorName.JIRA_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "clickup-connector",
				title: "ClickUp",
				description: "clickup_desc",
				icon: getConnectorIcon(EnumConnectorName.CLICKUP_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "knowledge-bases",
		title: "knowledge_bases",
		connectors: [
			{
				id: "notion-connector",
				title: "Notion",
				description: "notion_desc",
				icon: getConnectorIcon(EnumConnectorName.NOTION_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "github-connector",
				title: "GitHub",
				description: "github_desc",
				icon: getConnectorIcon(EnumConnectorName.GITHUB_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "confluence-connector",
				title: "Confluence",
				description: "confluence_desc",
				icon: getConnectorIcon(EnumConnectorName.CONFLUENCE_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "airtable-connector",
				title: "Airtable",
				description: "airtable_desc",
				icon: getConnectorIcon(EnumConnectorName.AIRTABLE_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "luma-connector",
				title: "Luma",
				description: "luma_desc",
				icon: getConnectorIcon(EnumConnectorName.LUMA_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "communication",
		title: "communication",
		connectors: [
			{
				id: "google-calendar-connector",
				title: "Google Calendar",
				description: "calendar_desc",
				icon: getConnectorIcon(EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "google-gmail-connector",
				title: "Gmail",
				description: "gmail_desc",
				icon: getConnectorIcon(EnumConnectorName.GOOGLE_GMAIL_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "zoom",
				title: "Zoom",
				description: "zoom_desc",
				icon: <IconBrandZoom className="h-6 w-6" />,
				status: "coming-soon",
			},
		],
	},
];
