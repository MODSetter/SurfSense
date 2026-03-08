"use client";

import { useEffect, useRef, useState } from "react";
import { useElectricClient } from "@/lib/electric/context";

/**
 * Returns whether any documents in the search space are currently being
 * uploaded or indexed (status = "pending" | "processing").
 *
 * Covers both manual file uploads (2-phase pattern) and all connector indexers,
 * since both create documents with status = pending before processing.
 *
 * The sync shape uses the same columns as useDocuments so Electric can share
 * the subscription when both hooks are active simultaneously.
 */
export function useDocumentsProcessing(searchSpaceId: number | null): boolean {
	const electricClient = useElectricClient();
	const [isProcessing, setIsProcessing] = useState(false);
	const liveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);

	useEffect(() => {
		if (!searchSpaceId || !electricClient) return;

		const spaceId = searchSpaceId;
		const client = electricClient;
		let mounted = true;

		async function setup() {
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may be closed */
				}
				liveQueryRef.current = null;
			}

			try {
				const handle = await client.syncShape({
					table: "documents",
					where: `search_space_id = ${spaceId}`,
					columns: [
						"id",
						"document_type",
						"search_space_id",
						"title",
						"created_by_id",
						"created_at",
						"status",
					],
					primaryKey: ["id"],
				});

				if (!mounted) return;

				if (!handle.isUpToDate && handle.initialSyncPromise) {
					await Promise.race([
						handle.initialSyncPromise,
						new Promise((resolve) => setTimeout(resolve, 5000)),
					]);
				}

				if (!mounted) return;

				const db = client.db as {
					live?: {
						query: <T>(
							sql: string,
							params?: (number | string)[]
						) => Promise<{
							subscribe: (cb: (result: { rows: T[] }) => void) => void;
							unsubscribe?: () => void;
						}>;
					};
				};

				if (!db.live?.query) return;

				const liveQuery = await db.live.query<{ count: number | string }>(
					`SELECT COUNT(*) as count FROM documents
					 WHERE search_space_id = $1
					 AND (status->>'state' = 'pending' OR status->>'state' = 'processing')`,
					[spaceId]
				);

				if (!mounted) {
					liveQuery.unsubscribe?.();
					return;
				}

				liveQuery.subscribe((result: { rows: Array<{ count: number | string }> }) => {
					if (!mounted || !result.rows?.[0]) return;
					setIsProcessing((Number(result.rows[0].count) || 0) > 0);
				});

				liveQueryRef.current = liveQuery;
			} catch (err) {
				console.error("[useDocumentsProcessing] Electric setup failed:", err);
			}
		}

		setup();

		return () => {
			mounted = false;
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may be closed */
				}
				liveQueryRef.current = null;
			}
		};
	}, [searchSpaceId, electricClient]);

	return isProcessing;
}
