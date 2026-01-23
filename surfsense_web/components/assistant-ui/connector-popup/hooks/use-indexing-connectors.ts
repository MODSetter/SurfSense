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
 * 2. Detecting in_progress notifications from Electric SQL to restore state after remounts
 * 3. Clearing indexing state when notifications become completed or failed
 * 4. Clearing indexing state when Electric SQL detects last_indexed_at changed
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

		for (const connector of connectors) {
			const previousValue = previousValues.get(connector.id);
			const currentValue = connector.last_indexed_at;

			// If last_indexed_at changed, clear it from indexing state
			if (
				previousValue !== undefined && // We've seen this connector before
				previousValue !== currentValue // Value changed
			) {
				// Use functional update to access current state
				setIndexingConnectorIds((prev) => {
					if (prev.has(connector.id)) {
						const next = new Set(prev);
						next.delete(connector.id);
						return next;
					}
					return prev;
				});
			}

			// Update previous value tracking
			previousValues.set(connector.id, currentValue);
		}
	}, [connectors]);

	// Detect notification status changes and update indexing state accordingly
	// This restores spinner state after component remounts and handles all status transitions
	useEffect(() => {
		if (!inboxItems || inboxItems.length === 0) return;

		setIndexingConnectorIds((prev) => {
			const newIndexingIds = new Set(prev);
			let hasChanges = false;

			for (const item of inboxItems) {
				// Only check connector_indexing notifications
				if (item.type !== "connector_indexing") continue;

				const metadata = isConnectorIndexingMetadata(item.metadata) ? item.metadata : null;
				if (!metadata) continue;

				// If status is "in_progress", add connector to indexing set
				if (metadata.status === "in_progress") {
					if (!newIndexingIds.has(metadata.connector_id)) {
						newIndexingIds.add(metadata.connector_id);
						hasChanges = true;
					}
				}
				// If status is "completed" or "failed", remove connector from indexing set
				else if (
					metadata.status === "completed" ||
					metadata.status === "failed" ||
					(metadata.error_message && metadata.error_message.trim().length > 0)
				) {
					if (newIndexingIds.has(metadata.connector_id)) {
						newIndexingIds.delete(metadata.connector_id);
						hasChanges = true;
					}
				}
			}

			return hasChanges ? newIndexingIds : prev;
		});
	}, [inboxItems]);

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
