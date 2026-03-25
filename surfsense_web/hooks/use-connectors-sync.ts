"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { queries } from "@/zero/queries";

/**
 * Syncs connectors for a search space via Zero.
 * Returns connectors, loading state, error, and a refresh function.
 */
export function useConnectorsSync(searchSpaceId: number | string | null) {
	const spaceId = searchSpaceId ? Number(searchSpaceId) : -1;

	const [data, result] = useQuery(queries.connectors.bySpace({ searchSpaceId: spaceId }));

	const connectors: SearchSourceConnector[] = useMemo(() => {
		if (!searchSpaceId || !data) return [];
		return data.map((c) => ({
			id: c.id,
			name: c.name,
			connector_type: c.connectorType as SearchSourceConnector["connector_type"],
			is_indexable: c.isIndexable,
			is_active: true,
			last_indexed_at: c.lastIndexedAt ? new Date(c.lastIndexedAt).toISOString() : null,
			config: (c.config as Record<string, unknown>) ?? {},
			enable_summary: c.enableSummary,
			periodic_indexing_enabled: c.periodicIndexingEnabled,
			indexing_frequency_minutes: c.indexingFrequencyMinutes ?? null,
			next_scheduled_at: c.nextScheduledAt ? new Date(c.nextScheduledAt).toISOString() : null,
			search_space_id: c.searchSpaceId,
			user_id: c.userId,
			created_at: c.createdAt ? new Date(c.createdAt).toISOString() : new Date().toISOString(),
		}));
	}, [searchSpaceId, data]);

	const loading = !searchSpaceId ? false : result.type !== "complete";
	const error = !searchSpaceId ? null : null;

	const refreshConnectors = async () => {};

	return { connectors, loading, error, refreshConnectors };
}
