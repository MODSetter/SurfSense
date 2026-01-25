"use client";

import type { FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { BaiduSearchApiConfig } from "./components/baidu-search-api-config";
import { BookStackConfig } from "./components/bookstack-config";
import { CirclebackConfig } from "./components/circleback-config";
import { ClickUpConfig } from "./components/clickup-config";
import { ComposioCalendarConfig } from "./components/composio-calendar-config";
import { ComposioDriveConfig } from "./components/composio-drive-config";
import { ComposioGmailConfig } from "./components/composio-gmail-config";
import { ConfluenceConfig } from "./components/confluence-config";
import { DiscordConfig } from "./components/discord-config";
import { ElasticsearchConfig } from "./components/elasticsearch-config";
import { GithubConfig } from "./components/github-config";
import { GoogleDriveConfig } from "./components/google-drive-config";
import { JiraConfig } from "./components/jira-config";
import { LinkupApiConfig } from "./components/linkup-api-config";
import { LumaConfig } from "./components/luma-config";
import { MCPConfig } from "./components/mcp-config";
import { ObsidianConfig } from "./components/obsidian-config";
import { SearxngConfig } from "./components/searxng-config";
import { SlackConfig } from "./components/slack-config";
import { TavilyApiConfig } from "./components/tavily-api-config";
import { TeamsConfig } from "./components/teams-config";
import { WebcrawlerConfig } from "./components/webcrawler-config";

export interface ConnectorConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
	searchSpaceId?: string;
}

export type ConnectorConfigComponent = FC<ConnectorConfigProps>;

/**
 * Factory function to get the appropriate config component for a connector type
 */
export function getConnectorConfigComponent(
	connectorType: string
): ConnectorConfigComponent | null {
	switch (connectorType) {
		case "GOOGLE_DRIVE_CONNECTOR":
			return GoogleDriveConfig;
		case "TAVILY_API":
			return TavilyApiConfig;
		case "SEARXNG_API":
			return SearxngConfig;
		case "LINKUP_API":
			return LinkupApiConfig;
		case "BAIDU_SEARCH_API":
			return BaiduSearchApiConfig;
		case "WEBCRAWLER_CONNECTOR":
			return WebcrawlerConfig;
		case "ELASTICSEARCH_CONNECTOR":
			return ElasticsearchConfig;
		case "SLACK_CONNECTOR":
			return SlackConfig;
		case "DISCORD_CONNECTOR":
			return DiscordConfig;
		case "TEAMS_CONNECTOR":
			return TeamsConfig;
		case "CONFLUENCE_CONNECTOR":
			return ConfluenceConfig;
		case "BOOKSTACK_CONNECTOR":
			return BookStackConfig;
		case "GITHUB_CONNECTOR":
			return GithubConfig;
		case "JIRA_CONNECTOR":
			return JiraConfig;
		case "CLICKUP_CONNECTOR":
			return ClickUpConfig;
		case "LUMA_CONNECTOR":
			return LumaConfig;
		case "CIRCLEBACK_CONNECTOR":
			return CirclebackConfig;
		case "MCP_CONNECTOR":
			return MCPConfig;
		case "OBSIDIAN_CONNECTOR":
			return ObsidianConfig;
		case "COMPOSIO_GOOGLE_DRIVE_CONNECTOR":
			return ComposioDriveConfig;
		case "COMPOSIO_GMAIL_CONNECTOR":
			return ComposioGmailConfig;
		case "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR":
			return ComposioCalendarConfig;
		// OAuth connectors (Gmail, Calendar, Airtable, Notion) and others don't need special config UI
		default:
			return null;
	}
}
