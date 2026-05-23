import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import {
	OAUTH_CONNECTORS,
	COMPOSIO_CONNECTORS,
	CRAWLERS,
	OTHER_CONNECTORS,
} from "@/components/assistant-ui/connector-popup/constants/connector-constants";

// =============================================================================
// Connector Telemetry Types & Registry
// =============================================================================

export type ConnectorTelemetryGroup =
	| "oauth"
	| "composio"
	| "crawler"
	| "other"
	| "unknown";

export interface ConnectorTelemetryMeta {
	connector_type: string;
	connector_title: string;
	connector_group: ConnectorTelemetryGroup;
	is_oauth: boolean;
}

/**
 * Single source of truth for "what does this connector_type look like in
 * analytics?". Any connector added to the lists above is automatically
 * picked up here, so adding a new integration does NOT require touching
 * `lib/posthog/events.ts` or per-connector tracking code.
 */
const CONNECTOR_TELEMETRY_REGISTRY: ReadonlyMap<
	string,
	ConnectorTelemetryMeta
> = (() => {
	const map = new Map<string, ConnectorTelemetryMeta>();

	for (const c of OAUTH_CONNECTORS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "oauth",
			is_oauth: true,
		});
	}
	for (const c of COMPOSIO_CONNECTORS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "composio",
			is_oauth: true,
		});
	}
	for (const c of CRAWLERS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "crawler",
			is_oauth: false,
		});
	}
	for (const c of OTHER_CONNECTORS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "other",
			is_oauth: false,
		});
	}

	return map;
})();

/**
 * Returns telemetry metadata for a connector_type, or a minimal "unknown"
 * record so tracking never no-ops for connectors that exist in the backend
 * but were forgotten in the UI registry.
 */
export function getConnectorTelemetryMeta(
	connectorType: string,
): ConnectorTelemetryMeta {
	const hit = CONNECTOR_TELEMETRY_REGISTRY.get(connectorType);
	if (hit) return hit;

	return {
		connector_type: connectorType,
		connector_title: connectorType,
		connector_group: "unknown",
		is_oauth: false,
	};
}

// =============================================================================
// Reauth Endpoint Resolution
// =============================================================================

/**
 * Legacy (non-MCP) OAuth reauth endpoints, keyed by connector type.
 * These are used for connectors that were NOT created via MCP OAuth.
 */
const LEGACY_REAUTH_ENDPOINTS: Partial<Record<string, string>> = {
	[EnumConnectorName.LINEAR_CONNECTOR]:
		"/api/v1/auth/linear/connector/reauth",
	[EnumConnectorName.JIRA_CONNECTOR]:
		"/api/v1/auth/jira/connector/reauth",
	[EnumConnectorName.NOTION_CONNECTOR]:
		"/api/v1/auth/notion/connector/reauth",
	[EnumConnectorName.GOOGLE_DRIVE_CONNECTOR]:
		"/api/v1/auth/google/drive/connector/reauth",
	[EnumConnectorName.GOOGLE_GMAIL_CONNECTOR]:
		"/api/v1/auth/google/gmail/connector/reauth",
	[EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR]:
		"/api/v1/auth/google/calendar/connector/reauth",
	[EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR]:
		"/api/v1/auth/composio/connector/reauth",
	[EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR]:
		"/api/v1/auth/composio/connector/reauth",
	[EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR]:
		"/api/v1/auth/composio/connector/reauth",
	[EnumConnectorName.ONEDRIVE_CONNECTOR]:
		"/api/v1/auth/onedrive/connector/reauth",
	[EnumConnectorName.DROPBOX_CONNECTOR]:
		"/api/v1/auth/dropbox/connector/reauth",
	[EnumConnectorName.CONFLUENCE_CONNECTOR]:
		"/api/v1/auth/confluence/connector/reauth",
	[EnumConnectorName.TEAMS_CONNECTOR]:
		"/api/v1/auth/teams/connector/reauth",
	[EnumConnectorName.DISCORD_CONNECTOR]:
		"/api/v1/auth/discord/connector/reauth",
};

/**
 * Resolve the reauth endpoint for a connector.
 *
 * MCP OAuth connectors (those with ``config.mcp_service``) dynamically build
 * the URL from the service key. Legacy OAuth connectors fall back to the
 * static ``LEGACY_REAUTH_ENDPOINTS`` map.
 */
export function getReauthEndpoint(
	connector: SearchSourceConnector,
): string | undefined {
	const mcpService = connector.config?.mcp_service as string | undefined;
	if (mcpService) {
		return `/api/v1/auth/mcp/${mcpService}/connector/reauth`;
	}
	return LEGACY_REAUTH_ENDPOINTS[connector.connector_type];
}
