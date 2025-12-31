/**
 * Helper function to get connector-specific benefits list
 * Returns null if no benefits are defined for the connector
 */
export function getConnectorBenefits(connectorType: string): string[] | null {
	const benefits: Record<string, string[]> = {
		LINEAR_CONNECTOR: [
			"Search through all your Linear issues and comments",
			"Access issue titles, descriptions, and full discussion threads",
			"Connect your team's project management directly to your search space",
			"Keep your search results up-to-date with latest Linear content",
			"Index your Linear issues for enhanced search capabilities",
		],
		// Add other connectors as needed
		// TAVILY_API: [...],
		// GITHUB_CONNECTOR: [...],
	};

	return benefits[connectorType] || null;
}

