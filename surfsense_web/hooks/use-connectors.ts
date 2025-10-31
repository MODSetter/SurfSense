// Types for connector API
export interface ConnectorConfig {
	[key: string]: string;
}

export interface Connector {
	id: number;
	name: string;
	connector_type: string;
	config: ConnectorConfig;
	created_at: string;
	user_id: string;
}

export interface CreateConnectorRequest {
	name: string;
	connector_type: string;
	config: ConnectorConfig;
}

// Get connector type display name
export const getConnectorTypeDisplay = (type: string): string => {
	const typeMap: Record<string, string> = {
		SERPER_API: "Serper API",
		TAVILY_API: "Tavily API",
		SEARXNG_API: "SearxNG",
	};
	return typeMap[type] || type;
};

// API service for connectors
export const ConnectorService = {
	// Create a new connector
	async createConnector(data: CreateConnectorRequest): Promise<Connector> {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors`,
			{
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
				},
				body: JSON.stringify(data),
			}
		);

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(errorData.detail || "Failed to create connector");
		}

		return response.json();
	},

	// Get all connectors
	async getConnectors(skip = 0, limit = 100): Promise<Connector[]> {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors?skip=${skip}&limit=${limit}`,
			{
				headers: {
					Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
				},
			}
		);

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(errorData.detail || "Failed to fetch connectors");
		}

		return response.json();
	},

	// Get a specific connector
	async getConnector(connectorId: number): Promise<Connector> {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
			{
				headers: {
					Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
				},
			}
		);

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(errorData.detail || "Failed to fetch connector");
		}

		return response.json();
	},

	// Update a connector
	async updateConnector(connectorId: number, data: CreateConnectorRequest): Promise<Connector> {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
			{
				method: "PUT",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
				},
				body: JSON.stringify(data),
			}
		);

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(errorData.detail || "Failed to update connector");
		}

		return response.json();
	},

	// Delete a connector
	async deleteConnector(connectorId: number): Promise<void> {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
			{
				method: "DELETE",
				headers: {
					Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
				},
			}
		);

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(errorData.detail || "Failed to delete connector");
		}
	},
};
