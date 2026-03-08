"use client";

import { useEffect, useRef, useState } from "react";
import { useElectricClient } from "@/lib/electric/context";

export type DocumentsProcessingStatus = "idle" | "processing" | "success" | "error";

const SUCCESS_LINGER_MS = 5000;

/**
 * Returns the processing status of documents in the search space:
 *   - "processing" — at least one doc is pending/processing (show spinner)
 *   - "error"      — nothing processing, but failed docs exist (show red icon)
 *   - "success"    — just transitioned from processing → all clear (green check, auto-dismisses)
 *   - "idle"       — nothing noteworthy (show normal icon)
 */
export function useDocumentsProcessing(searchSpaceId: number | null): DocumentsProcessingStatus {
	const electricClient = useElectricClient();
	const [status, setStatus] = useState<DocumentsProcessingStatus>("idle");
	const liveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);
	const wasProcessingRef = useRef(false);
	const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

				const liveQuery = await db.live.query<{
					processing_count: number | string;
					failed_count: number | string;
				}>(
					`SELECT
						SUM(CASE WHEN status->>'state' IN ('pending', 'processing') THEN 1 ELSE 0 END) AS processing_count,
						SUM(CASE WHEN status->>'state' = 'failed' THEN 1 ELSE 0 END) AS failed_count
					 FROM documents
					 WHERE search_space_id = $1`,
					[spaceId]
				);

				if (!mounted) {
					liveQuery.unsubscribe?.();
					return;
				}

				liveQuery.subscribe(
					(result: {
						rows: Array<{ processing_count: number | string; failed_count: number | string }>;
					}) => {
						if (!mounted || !result.rows?.[0]) return;

						const processingCount = Number(result.rows[0].processing_count) || 0;
						const failedCount = Number(result.rows[0].failed_count) || 0;

						if (processingCount > 0) {
							wasProcessingRef.current = true;
							if (successTimerRef.current) {
								clearTimeout(successTimerRef.current);
								successTimerRef.current = null;
							}
							setStatus("processing");
						} else if (failedCount > 0) {
							wasProcessingRef.current = false;
							if (successTimerRef.current) {
								clearTimeout(successTimerRef.current);
								successTimerRef.current = null;
							}
							setStatus("error");
						} else if (wasProcessingRef.current) {
							wasProcessingRef.current = false;
							setStatus("success");
							if (successTimerRef.current) {
								clearTimeout(successTimerRef.current);
							}
							successTimerRef.current = setTimeout(() => {
								if (mounted) {
									setStatus("idle");
									successTimerRef.current = null;
								}
							}, SUCCESS_LINGER_MS);
						} else {
							setStatus("idle");
						}
					}
				);

				liveQueryRef.current = liveQuery;
			} catch (err) {
				console.error("[useDocumentsProcessing] Electric setup failed:", err);
			}
		}

		setup();

		return () => {
			mounted = false;
			if (successTimerRef.current) {
				clearTimeout(successTimerRef.current);
				successTimerRef.current = null;
			}
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

	return status;
}
