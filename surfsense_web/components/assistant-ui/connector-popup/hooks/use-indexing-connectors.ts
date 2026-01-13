"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

/**
 * Hook to track which connectors are currently indexing using local state.
 *
 * This provides a better UX than polling by:
 * 1. Setting indexing state immediately when user triggers indexing (optimistic)
 * 2. Clearing indexing state when Electric SQL detects last_indexed_at changed
 *
 * The actual `last_indexed_at` value comes from Electric SQL/PGlite, not local state.
 */
export function useIndexingConnectors(connectors: SearchSourceConnector[]) {
	// Set of connector IDs that are currently indexing
	const [indexingConnectorIds, setIndexingConnectorIds] = useState<Set<number>>(new Set());

	// Track previous last_indexed_at values to detect changes
	const previousLastIndexedAtRef = useRef<Map<number, string | null>>(new Map());

	// Detect when last_indexed_at changes (indexing completed) via Electric SQL
	useEffect(() => {
		const previousValues = previousLastIndexedAtRef.current;
		const newIndexingIds = new Set(indexingConnectorIds);
		let hasChanges = false;

		for (const connector of connectors) {
			const previousValue = previousValues.get(connector.id);
			const currentValue = connector.last_indexed_at;

			// If last_indexed_at changed and connector was in indexing state, clear it
			if (
				previousValue !== undefined && // We've seen this connector before
				previousValue !== currentValue && // Value changed
				indexingConnectorIds.has(connector.id) // It was marked as indexing
			) {
				newIndexingIds.delete(connector.id);
				hasChanges = true;
			}

			// Update previous value tracking
			previousValues.set(connector.id, currentValue);
		}

		if (hasChanges) {
			setIndexingConnectorIds(newIndexingIds);
		}
	}, [connectors, indexingConnectorIds]);

	// Add a connector to the indexing set (called when indexing starts)
	const startIndexing = useCallback((connectorId: number) => {
		setIndexingConnectorIds((prev) => {
			const next = new Set(prev);
			next.add(connectorId);
			return next;
		});
	}, []);

	// Remove a connector from the indexing set (called manually if needed)
	const stopIndexing = useCallback((connectorId: number) => {
		setIndexingConnectorIds((prev) => {
			const next = new Set(prev);
			next.delete(connectorId);
			return next;
		});
	}, []);

	// Check if a connector is currently indexing
	const isIndexing = useCallback(
		(connectorId: number) => indexingConnectorIds.has(connectorId),
		[indexingConnectorIds]
	);

	return {
		indexingConnectorIds,
		startIndexing,
		stopIndexing,
		isIndexing,
	};
}
