import { table, string, number, boolean, json } from "@rocicorp/zero";

export const documentTable = table("documents")
	.columns({
		id: number(),
		title: string(),
		documentType: string().from("document_type"),
		searchSpaceId: number().from("search_space_id"),
		createdById: string().optional().from("created_by_id"),
		status: json(),
		createdAt: number().from("created_at"),
	})
	.primaryKey("id");

export const searchSourceConnectorTable = table("search_source_connectors")
	.columns({
		id: number(),
		name: string(),
		connectorType: string().from("connector_type"),
		isIndexable: boolean().from("is_indexable"),
		lastIndexedAt: number().optional().from("last_indexed_at"),
		config: json(),
		enableSummary: boolean().from("enable_summary"),
		periodicIndexingEnabled: boolean().from("periodic_indexing_enabled"),
		indexingFrequencyMinutes: number().optional().from("indexing_frequency_minutes"),
		nextScheduledAt: number().optional().from("next_scheduled_at"),
		searchSpaceId: number().from("search_space_id"),
		userId: string().from("user_id"),
		createdAt: number().from("created_at"),
	})
	.primaryKey("id");
