import { useCallback, useEffect, useState } from "react";

export interface SearchSourceConnector {
	id: number;
	name: string;
	connector_type: string;
	is_indexable: boolean;
	last_indexed_at: string | null;
	config: Record<string, any>;
	search_space_id: number;
	user_id?: string;
	created_at?: string;
	periodic_indexing_enabled: boolean;
	indexing_frequency_minutes: number | null;
	next_scheduled_at: string | null;
}

export interface ConnectorSourceItem {
	id: number;
	name: string;
	type: string;
	sources: any[];
}

/**
 * Hook to fetch search source connectors from the API
 * @param lazy - If true, connectors won't be fetched on mount
 * @param searchSpaceId - Optional search space ID to filter connectors
 */
export const useSearchSourceConnectors = (lazy: boolean = false, searchSpaceId?: number) => {
	const [connectors, setConnectors] = useState<SearchSourceConnector[]>([]);
	const [isLoading, setIsLoading] = useState(!lazy); // Don't show loading initially for lazy mode
	const [isLoaded, setIsLoaded] = useState(false); // Memoization flag
	const [error, setError] = useState<Error | null>(null);
	const [connectorSourceItems, setConnectorSourceItems] = useState<ConnectorSourceItem[]>([
		{
			id: 1,
			name: "Crawled URL",
			type: "CRAWLED_URL",
			sources: [],
		},
		{
			id: 2,
			name: "File",
			type: "FILE",
			sources: [],
		},
		{
			id: 3,
			name: "Extension",
			type: "EXTENSION",
			sources: [],
		},
		{
			id: 4,
			name: "Youtube Video",
			type: "YOUTUBE_VIDEO",
			sources: [],
		},
	]);

	const fetchConnectors = useCallback(
		async (spaceId?: number) => {
			if (isLoaded && lazy) return; // Avoid redundant calls in lazy mode

			try {
				setIsLoading(true);
				setError(null);
				const token = localStorage.getItem("surfsense_bearer_token");

				if (!token) {
					throw new Error("No authentication token found");
				}

				// Build URL with optional search_space_id query parameter
				const url = new URL(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors`
				);
				if (spaceId !== undefined) {
					url.searchParams.append("search_space_id", spaceId.toString());
				}

				const response = await fetch(url.toString(), {
					method: "GET",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
				});

				if (!response.ok) {
					throw new Error(`Failed to fetch connectors: ${response.statusText}`);
				}

				const data = await response.json();
				setConnectors(data);
				setIsLoaded(true);

				// Update connector source items when connectors change
				updateConnectorSourceItems(data);

				return data;
			} catch (err) {
				setError(err instanceof Error ? err : new Error("An unknown error occurred"));
				console.error("Error fetching search source connectors:", err);
			} finally {
				setIsLoading(false);
			}
		},
		[isLoaded, lazy]
	);

	useEffect(() => {
		if (!lazy) {
			fetchConnectors(searchSpaceId);
		}
	}, [lazy, fetchConnectors, searchSpaceId]);

	// Function to refresh the connectors list
	const refreshConnectors = useCallback(
		async (spaceId?: number) => {
			setIsLoaded(false); // Reset memoization flag to allow refetch
			await fetchConnectors(spaceId !== undefined ? spaceId : searchSpaceId);
		},
		[fetchConnectors, searchSpaceId]
	);

	// Update connector source items when connectors change
	const updateConnectorSourceItems = (currentConnectors: SearchSourceConnector[]) => {
		// Start with the default hardcoded connectors
		const defaultConnectors: ConnectorSourceItem[] = [
			{
				id: 1,
				name: "Crawled URL",
				type: "CRAWLED_URL",
				sources: [],
			},
			{
				id: 2,
				name: "File",
				type: "FILE",
				sources: [],
			},
			{
				id: 3,
				name: "Extension",
				type: "EXTENSION",
				sources: [],
			},
			{
				id: 4,
				name: "Youtube Video",
				type: "YOUTUBE_VIDEO",
				sources: [],
			},
		];

		// Add the API connectors
		const apiConnectors: ConnectorSourceItem[] = currentConnectors.map((connector, index) => ({
			id: 1000 + index, // Use a high ID to avoid conflicts with hardcoded IDs
			name: connector.name,
			type: connector.connector_type,
			sources: [],
		}));

		setConnectorSourceItems([...defaultConnectors, ...apiConnectors]);
	};

	/**
	 * Create a new search source connector
	 * @param connectorData - The connector data (excluding search_space_id)
	 * @param spaceId - The search space ID to associate the connector with
	 */
	const createConnector = async (
		connectorData: Omit<SearchSourceConnector, "id" | "user_id" | "created_at" | "search_space_id">,
		spaceId: number
	) => {
		try {
			const token = localStorage.getItem("surfsense_bearer_token");

			if (!token) {
				throw new Error("No authentication token found");
			}

			// Add search_space_id as a query parameter
			const url = new URL(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors`
			);
			url.searchParams.append("search_space_id", spaceId.toString());

			const response = await fetch(url.toString(), {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${token}`,
				},
				body: JSON.stringify(connectorData),
			});

			if (!response.ok) {
				throw new Error(`Failed to create connector: ${response.statusText}`);
			}

			const newConnector = await response.json();
			const updatedConnectors = [...connectors, newConnector];
			setConnectors(updatedConnectors);
			updateConnectorSourceItems(updatedConnectors);
			return newConnector;
		} catch (err) {
			console.error("Error creating search source connector:", err);
			throw err;
		}
	};

	/**
	 * Update an existing search source connector
	 */
	const updateConnector = async (
		connectorId: number,
		connectorData: Partial<
			Omit<SearchSourceConnector, "id" | "user_id" | "created_at" | "search_space_id">
		>
	) => {
		try {
			const token = localStorage.getItem("surfsense_bearer_token");

			if (!token) {
				throw new Error("No authentication token found");
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
				{
					method: "PUT",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify(connectorData),
				}
			);

			if (!response.ok) {
				throw new Error(`Failed to update connector: ${response.statusText}`);
			}

			const updatedConnector = await response.json();
			const updatedConnectors = connectors.map((connector) =>
				connector.id === connectorId ? updatedConnector : connector
			);
			setConnectors(updatedConnectors);
			updateConnectorSourceItems(updatedConnectors);
			return updatedConnector;
		} catch (err) {
			console.error("Error updating search source connector:", err);
			throw err;
		}
	};

	/**
	 * Delete a search source connector
	 */
	const deleteConnector = async (connectorId: number) => {
		try {
			const token = localStorage.getItem("surfsense_bearer_token");

			if (!token) {
				throw new Error("No authentication token found");
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
				{
					method: "DELETE",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
				}
			);

			if (!response.ok) {
				throw new Error(`Failed to delete connector: ${response.statusText}`);
			}

			const updatedConnectors = connectors.filter((connector) => connector.id !== connectorId);
			setConnectors(updatedConnectors);
			updateConnectorSourceItems(updatedConnectors);
		} catch (err) {
			console.error("Error deleting search source connector:", err);
			throw err;
		}
	};

	/**
	 * Index content from a connector to a search space
	 */
	const indexConnector = async (
		connectorId: number,
		searchSpaceId: string | number,
		startDate?: string,
		endDate?: string
	) => {
		try {
			const token = localStorage.getItem("surfsense_bearer_token");

			if (!token) {
				throw new Error("No authentication token found");
			}

			// Build query parameters
			const params = new URLSearchParams({
				search_space_id: searchSpaceId.toString(),
			});
			if (startDate) {
				params.append("start_date", startDate);
			}
			if (endDate) {
				params.append("end_date", endDate);
			}

			const response = await fetch(
				`${
					process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL
				}/api/v1/search-source-connectors/${connectorId}/index?${params.toString()}`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
				}
			);

			if (!response.ok) {
				throw new Error(`Failed to index connector content: ${response.statusText}`);
			}

			const result = await response.json();

			// Update the connector's last_indexed_at timestamp
			const updatedConnectors = connectors.map((connector) =>
				connector.id === connectorId
					? {
							...connector,
							last_indexed_at: new Date().toISOString(),
						}
					: connector
			);
			setConnectors(updatedConnectors);

			return result;
		} catch (err) {
			console.error("Error indexing connector content:", err);
			throw err;
		}
	};

	/**
	 * Get connector source items - memoized to prevent unnecessary re-renders
	 */
	const getConnectorSourceItems = useCallback(() => {
		return connectorSourceItems;
	}, [connectorSourceItems]);

	return {
		connectors,
		isLoading,
		isLoaded,
		error,
		fetchConnectors,
		createConnector,
		updateConnector,
		deleteConnector,
		indexConnector,
		getConnectorSourceItems,
		connectorSourceItems,
		refreshConnectors,
	};
};
