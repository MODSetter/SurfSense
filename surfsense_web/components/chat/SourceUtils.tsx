import type { Connector, Source } from "./types";

/**
 * Function to get sources for the main view
 */
export const getMainViewSources = (connector: Connector, initialSourcesDisplay: number) => {
	return connector.sources?.slice(0, initialSourcesDisplay);
};

/**
 * Function to get filtered sources for the dialog
 */
export const getFilteredSources = (connector: Connector, sourceFilter: string) => {
	if (!sourceFilter.trim()) {
		return connector.sources;
	}

	const filter = sourceFilter.toLowerCase().trim();
	return connector.sources?.filter(
		(source) =>
			source.title.toLowerCase().includes(filter) ||
			source.description.toLowerCase().includes(filter)
	);
};

/**
 * Function to get paginated and filtered sources for the dialog
 */
export const getPaginatedDialogSources = (
	connector: Connector,
	sourceFilter: string,
	expandedSources: boolean,
	sourcesPage: number,
	sourcesPerPage: number
) => {
	const filteredSources = getFilteredSources(connector, sourceFilter);

	if (expandedSources) {
		return filteredSources;
	}
	return filteredSources?.slice(0, sourcesPage * sourcesPerPage);
};

/**
 * Function to get the count of sources for a connector type
 */
export const getSourcesCount = (connectorSources: Connector[], connectorType: string) => {
	const connector = connectorSources.find((c) => c.type === connectorType);
	return connector?.sources?.length || 0;
};

/**
 * Function to get a citation source by ID
 */
export const getCitationSource = (
	citationId: number,
	connectorSources: Connector[]
): Source | null => {
	for (const connector of connectorSources) {
		const source = connector.sources?.find((s) => s.id === citationId);
		if (source) {
			return {
				...source,
				connectorType: connector.type,
			};
		}
	}
	return null;
};
