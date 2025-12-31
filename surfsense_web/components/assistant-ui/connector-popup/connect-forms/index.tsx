import type { FC } from "react";
import { ElasticsearchConnectForm } from "./components/elasticsearch-connect-form";
import { LinearConnectForm } from "./components/linear-connect-form";
import { TavilyApiConnectForm } from "./components/tavily-api-connect-form";

export interface ConnectFormProps {
	onSubmit: (data: {
		name: string;
		connector_type: string;
		config: Record<string, unknown>;
		is_indexable: boolean;
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
export function getConnectFormComponent(
	connectorType: string
): ConnectFormComponent | null {
	switch (connectorType) {
		case "TAVILY_API":
			return TavilyApiConnectForm;
		case "LINEAR_CONNECTOR":
			return LinearConnectForm;
		case "ELASTICSEARCH_CONNECTOR":
			return ElasticsearchConnectForm;
		// Add other connector types here as needed
		default:
			return null;
	}
}

