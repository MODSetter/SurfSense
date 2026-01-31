"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { InboxItem } from "@/contracts/types/inbox.types";
import { isConnectorIndexingMetadata } from "@/contracts/types/inbox.types";

/**
 * Timeout thresholds for stuck task detection
 *
 * These align with the backend Celery configuration:
 * - HARD_TIMEOUT: 8 hours (task_time_limit=28800 in Celery)
 *   Any task running longer than this is definitely dead.
 *
 * - STALE_THRESHOLD: 15 minutes without notification updates
 *   If heartbeats are being sent every 30s, missing 15+ minutes of updates
 *   indicates the task has likely crashed or the worker is down.
 */
const HARD_TIMEOUT_MS = 8 * 60 * 60 * 1000; // 8 hours in milliseconds
const STALE_THRESHOLD_MS = 15 * 60 * 1000; // 15 minutes in milliseconds

/**
 * Check if a notification is stale (no updates for too long)
 * @param updatedAt - ISO timestamp of last notification update
 * @returns true if the notification hasn't been updated recently
 */
function isNotificationStale(updatedAt: string | null | undefined): boolean {
	if (!updatedAt) return false;
	const lastUpdate = new Date(updatedAt).getTime();
	const now = Date.now();
	return now - lastUpdate > STALE_THRESHOLD_MS;
}

/**
 * Check if a task has exceeded the hard timeout (definitely dead)
 * @param startedAt - ISO timestamp when the task started
 * @returns true if the task has been running longer than the hard limit
 */
function isTaskTimedOut(startedAt: string | null | undefined): boolean {
	if (!startedAt) return false;
	const startTime = new Date(startedAt).getTime();
	const now = Date.now();
	return now - startTime > HARD_TIMEOUT_MS;
}

/**
 * Hook to track which connectors are currently indexing using local state.
 *
 * This provides a better UX than polling by:
 * 1. Setting indexing state immediately when user triggers indexing (optimistic)
 * 2. Detecting in_progress notifications from Electric SQL to restore state after remounts
 * 3. Clearing indexing state when notifications become completed or failed
 * 4. Clearing indexing state when Electric SQL detects last_indexed_at changed
 * 5. Detecting stale/stuck tasks that haven't updated in 15+ minutes
 * 6. Detecting hard timeout (8h) - tasks that definitely cannot still be running
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
	// Also detects stale/stuck tasks that haven't been updated in a while
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

				// If status is "in_progress", check if it's actually still running
				if (metadata.status === "in_progress") {
					// Check for hard timeout (8h) - task is definitely dead
					const timedOut = isTaskTimedOut(metadata.started_at);

					// Check for stale notification (15min without updates) - task likely crashed
					const stale = isNotificationStale(item.updated_at);

					if (timedOut || stale) {
						// Task is stuck - don't show as indexing
						if (newIndexingIds.has(metadata.connector_id)) {
							newIndexingIds.delete(metadata.connector_id);
							hasChanges = true;
						}
					} else {
						// Task appears to be genuinely running
						if (!newIndexingIds.has(metadata.connector_id)) {
							newIndexingIds.add(metadata.connector_id);
							hasChanges = true;
						}
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
