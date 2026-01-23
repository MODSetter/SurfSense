"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { InboxItem } from "@/contracts/types/inbox.types";
import { isConnectorIndexingMetadata } from "@/contracts/types/inbox.types";

/**
 * Hook to track which connectors are currently indexing using local state.
 *
 * This provides a better UX than polling by:
 * 1. Setting indexing state immediately when user triggers indexing (optimistic)
 * 2. Clearing indexing state when Electric SQL detects last_indexed_at changed
 * 3. Clearing indexing state when a failed notification is detected
 *
 * The actual `last_indexed_at` value comes from Electric SQL/PGlite, not local state.
 */
export function useIndexingConnectors(
	connectors: SearchSourceConnector[],
	inboxItems?: InboxItem[]
) {
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

	// Detect failed notifications and stop indexing state
	useEffect(() => {
		if (!inboxItems || inboxItems.length === 0) return;

		const newIndexingIds = new Set(indexingConnectorIds);
		let hasChanges = false;

		for (const item of inboxItems) {
			// Only check connector_indexing notifications
			if (item.type !== "connector_indexing") continue;

			// Check if this notification indicates a failure
			const metadata = isConnectorIndexingMetadata(item.metadata)
				? item.metadata
				: null;
			if (!metadata) continue;

			// Check if status is "failed" or if there's an error_message
			const isFailed =
				metadata.status === "failed" ||
				(metadata.error_message && metadata.error_message.trim().length > 0);

			// If failed and connector is in indexing state, clear it
			if (isFailed && indexingConnectorIds.has(metadata.connector_id)) {
				newIndexingIds.delete(metadata.connector_id);
				hasChanges = true;
			}
		}

		if (hasChanges) {
			setIndexingConnectorIds(newIndexingIds);
		}
	}, [inboxItems, indexingConnectorIds]);

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
