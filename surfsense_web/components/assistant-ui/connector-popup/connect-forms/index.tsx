import type { FC } from "react";
import { BaiduSearchApiConnectForm } from "./components/baidu-search-api-connect-form";
import { BookStackConnectForm } from "./components/bookstack-connect-form";
import { CirclebackConnectForm } from "./components/circleback-connect-form";
import { ElasticsearchConnectForm } from "./components/elasticsearch-connect-form";
import { GithubConnectForm } from "./components/github-connect-form";
import { LinkupApiConnectForm } from "./components/linkup-api-connect-form";
import { LumaConnectForm } from "./components/luma-connect-form";
import { MCPConnectForm } from "./components/mcp-connect-form";
import { ObsidianConnectForm } from "./components/obsidian-connect-form";
import { SearxngConnectForm } from "./components/searxng-connect-form";
import { TavilyApiConnectForm } from "./components/tavily-api-connect-form";

export interface ConnectFormProps {
	onSubmit: (data: {
		name: string;
		connector_type: string;
		config: Record<string, unknown>;
		is_indexable: boolean;
		is_active: boolean;
		last_indexed_at: null;
		periodic_indexing_enabled: boolean;
		indexing_frequency_minutes: number | null;
		next_scheduled_at: null;
		startDate?: Date;
		endDate?: Date;
		periodicEnabled?: boolean;
		frequencyMinutes?: string;
	}) => Promise<void>;
	onBack: () => void;
	isSubmitting: boolean;
	onFormSubmit?: () => void;
}

export type ConnectFormComponent = FC<ConnectFormProps>;

/**
 * Factory function to get the appropriate connect form component for a connector type
 */
export function getConnectFormComponent(connectorType: string): ConnectFormComponent | null {
	switch (connectorType) {
		case "TAVILY_API":
			return TavilyApiConnectForm;
		case "SEARXNG_API":
			return SearxngConnectForm;
		case "LINKUP_API":
			return LinkupApiConnectForm;
		case "BAIDU_SEARCH_API":
			return BaiduSearchApiConnectForm;
		case "ELASTICSEARCH_CONNECTOR":
			return ElasticsearchConnectForm;
		case "BOOKSTACK_CONNECTOR":
			return BookStackConnectForm;
		case "GITHUB_CONNECTOR":
			return GithubConnectForm;
		case "LUMA_CONNECTOR":
			return LumaConnectForm;
		case "CIRCLEBACK_CONNECTOR":
			return CirclebackConnectForm;
		case "MCP_CONNECTOR":
			return MCPConnectForm;
		case "OBSIDIAN_CONNECTOR":
			return ObsidianConnectForm;
		// Add other connector types here as needed
		default:
			return null;
	}
}
