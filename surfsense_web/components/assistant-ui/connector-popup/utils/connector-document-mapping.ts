"use client";

/**
 * Maps SearchSourceConnectorType to DocumentType for fetching document counts
 *
 * Note: Some connectors don't have a direct 1:1 mapping to document types:
 * - Search API connectors (TAVILY_API, SEARXNG_API, etc.) don't index documents
 * - WEBCRAWLER_CONNECTOR maps to CRAWLED_URL document type
 * - GOOGLE_DRIVE_CONNECTOR maps to GOOGLE_DRIVE_FILE document type
 */
export const CONNECTOR_TO_DOCUMENT_TYPE: Record<string, string> = {
	// Direct mappings (connector type matches document type)
	SLACK_CONNECTOR: "SLACK_CONNECTOR",
	TEAMS_CONNECTOR: "TEAMS_CONNECTOR",
	NOTION_CONNECTOR: "NOTION_CONNECTOR",
	GITHUB_CONNECTOR: "GITHUB_CONNECTOR",
	LINEAR_CONNECTOR: "LINEAR_CONNECTOR",
	DISCORD_CONNECTOR: "DISCORD_CONNECTOR",
	JIRA_CONNECTOR: "JIRA_CONNECTOR",
	CONFLUENCE_CONNECTOR: "CONFLUENCE_CONNECTOR",
	CLICKUP_CONNECTOR: "CLICKUP_CONNECTOR",
	GOOGLE_CALENDAR_CONNECTOR: "GOOGLE_CALENDAR_CONNECTOR",
	GOOGLE_GMAIL_CONNECTOR: "GOOGLE_GMAIL_CONNECTOR",
	AIRTABLE_CONNECTOR: "AIRTABLE_CONNECTOR",
	LUMA_CONNECTOR: "LUMA_CONNECTOR",
	ELASTICSEARCH_CONNECTOR: "ELASTICSEARCH_CONNECTOR",
	BOOKSTACK_CONNECTOR: "BOOKSTACK_CONNECTOR",
	CIRCLEBACK_CONNECTOR: "CIRCLEBACK",
	OBSIDIAN_CONNECTOR: "OBSIDIAN_CONNECTOR",

	// Special mappings (connector type differs from document type)
	GOOGLE_DRIVE_CONNECTOR: "GOOGLE_DRIVE_FILE",
	WEBCRAWLER_CONNECTOR: "CRAWLED_URL",
	// Composio connectors map to their own document types
	COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
	COMPOSIO_GMAIL_CONNECTOR: "COMPOSIO_GMAIL_CONNECTOR",
	COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
};

/**
 * Get the document type for a given connector type
 * Returns undefined if the connector doesn't index documents (e.g., search APIs)
 */
export function getDocumentTypeForConnector(connectorType: string): string | undefined {
	return CONNECTOR_TO_DOCUMENT_TYPE[connectorType];
}

/**
 * Get document count for a specific connector type from document type counts
 */
export function getDocumentCountForConnector(
	connectorType: string,
	documentTypeCounts: Record<string, number> | undefined
): number | undefined {
	if (!documentTypeCounts) return undefined;

	const documentType = getDocumentTypeForConnector(connectorType);
	if (!documentType) return undefined;

	return documentTypeCounts[documentType];
}

/**
 * Check if a connector type is indexable (produces documents)
 */
export function isIndexableConnectorType(connectorType: string): boolean {
	return connectorType in CONNECTOR_TO_DOCUMENT_TYPE;
}
