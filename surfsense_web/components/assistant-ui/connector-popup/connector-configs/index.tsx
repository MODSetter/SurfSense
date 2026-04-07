"use client";

import dynamic from "next/dynamic";
import type { FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

export interface ConnectorConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
	searchSpaceId?: string;
}

export type ConnectorConfigComponent = FC<ConnectorConfigProps>;

const configLoaders: Record<
	string,
	() => Promise<{ default: FC<ConnectorConfigProps> }>
> = {
	GOOGLE_DRIVE_CONNECTOR: () =>
		import("./components/google-drive-config").then((m) => ({
			default: m.GoogleDriveConfig,
		})),
	TAVILY_API: () =>
		import("./components/tavily-api-config").then((m) => ({
			default: m.TavilyApiConfig,
		})),
	LINKUP_API: () =>
		import("./components/linkup-api-config").then((m) => ({
			default: m.LinkupApiConfig,
		})),
	BAIDU_SEARCH_API: () =>
		import("./components/baidu-search-api-config").then((m) => ({
			default: m.BaiduSearchApiConfig,
		})),
	WEBCRAWLER_CONNECTOR: () =>
		import("./components/webcrawler-config").then((m) => ({
			default: m.WebcrawlerConfig,
		})),
	ELASTICSEARCH_CONNECTOR: () =>
		import("./components/elasticsearch-config").then((m) => ({
			default: m.ElasticsearchConfig,
		})),
	SLACK_CONNECTOR: () =>
		import("./components/slack-config").then((m) => ({
			default: m.SlackConfig,
		})),
	DISCORD_CONNECTOR: () =>
		import("./components/discord-config").then((m) => ({
			default: m.DiscordConfig,
		})),
	TEAMS_CONNECTOR: () =>
		import("./components/teams-config").then((m) => ({
			default: m.TeamsConfig,
		})),
	CONFLUENCE_CONNECTOR: () =>
		import("./components/confluence-config").then((m) => ({
			default: m.ConfluenceConfig,
		})),
	BOOKSTACK_CONNECTOR: () =>
		import("./components/bookstack-config").then((m) => ({
			default: m.BookStackConfig,
		})),
	GITHUB_CONNECTOR: () =>
		import("./components/github-config").then((m) => ({
			default: m.GithubConfig,
		})),
	JIRA_CONNECTOR: () =>
		import("./components/jira-config").then((m) => ({
			default: m.JiraConfig,
		})),
	CLICKUP_CONNECTOR: () =>
		import("./components/clickup-config").then((m) => ({
			default: m.ClickUpConfig,
		})),
	LUMA_CONNECTOR: () =>
		import("./components/luma-config").then((m) => ({
			default: m.LumaConfig,
		})),
	CIRCLEBACK_CONNECTOR: () =>
		import("./components/circleback-config").then((m) => ({
			default: m.CirclebackConfig,
		})),
	MCP_CONNECTOR: () =>
		import("./components/mcp-config").then((m) => ({
			default: m.MCPConfig,
		})),
	OBSIDIAN_CONNECTOR: () =>
		import("./components/obsidian-config").then((m) => ({
			default: m.ObsidianConfig,
		})),
	COMPOSIO_GOOGLE_DRIVE_CONNECTOR: () =>
		import("./components/composio-drive-config").then((m) => ({
			default: m.ComposioDriveConfig,
		})),
	COMPOSIO_GMAIL_CONNECTOR: () =>
		import("./components/composio-gmail-config").then((m) => ({
			default: m.ComposioGmailConfig,
		})),
	COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: () =>
		import("./components/composio-calendar-config").then((m) => ({
			default: m.ComposioCalendarConfig,
		})),
};

/**
 * Factory function to get the appropriate config component for a connector type
 */
export function getConnectorConfigComponent(
	connectorType: string
): ConnectorConfigComponent | null {
	const loader = configLoaders[connectorType];
	if (!loader) return null;

	return dynamic(loader, { ssr: false }) as unknown as ConnectorConfigComponent;
}
