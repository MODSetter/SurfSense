"use client";

import { useEffect, useState, useRef } from "react";
import { useElectricClient } from "@/lib/electric/context";
import type { SyncHandle } from "@/lib/electric/client";

export interface ElectricMention {
	id: number;
	comment_id: number;
	mentioned_user_id: string;
	created_at: string;
}

/**
 * Hook for syncing mentions with Electric SQL for real-time updates.
 * Syncs all mentions for the current user.
 * @param userId - The user ID to sync mentions for
 */
export function useMentionsElectric(userId: string | null) {
	const electricClient = useElectricClient();

	const [mentions, setMentions] = useState<ElectricMention[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const syncKeyRef = useRef<string | null>(null);

	useEffect(() => {
		if (!electricClient) {
			setLoading(false);
			setError(new Error("Electric SQL not configured"));
			return;
		}

		if (!userId) {
			setMentions([]);
			setLoading(false);
			return;
		}

		const syncKey = `mentions_${userId}`;
		if (syncKeyRef.current === syncKey) {
			return;
		}

		let mounted = true;
		syncKeyRef.current = syncKey;

		const client = electricClient;

		async function startSync() {
			try {
				const handle = await client.syncShape({
					table: "chat_comment_mentions",
					where: `mentioned_user_id = '${userId}'`,
					primaryKey: ["id"],
				});

				if (!handle.isUpToDate && handle.initialSyncPromise) {
					try {
						await Promise.race([
							handle.initialSyncPromise,
							new Promise((resolve) => setTimeout(resolve, 2000)),
						]);
					} catch (syncErr) {
						console.error("[useMentionsElectric] Initial sync failed:", syncErr);
					}
				}

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				setLoading(false);
				setError(null);

				await fetchMentions();
				await setupLiveQuery();
			} catch (err) {
				if (!mounted) return;
				console.error("[useMentionsElectric] Failed to start sync:", err);
				setError(err instanceof Error ? err : new Error("Failed to sync mentions"));
				setLoading(false);
			}
		}

		async function fetchMentions() {
			try {
				const result = await client.db.query<ElectricMention>(
					`SELECT id, comment_id, mentioned_user_id, created_at 
					 FROM chat_comment_mentions 
					 WHERE mentioned_user_id = $1 
					 ORDER BY created_at DESC`,
					[userId]
				);
				if (mounted) {
					setMentions(result.rows || []);
				}
			} catch (err) {
				console.error("[useMentionsElectric] Failed to fetch:", err);
			}
		}

		async function setupLiveQuery() {
			try {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = client.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(
						`SELECT id, comment_id, mentioned_user_id, created_at 
						 FROM chat_comment_mentions 
						 WHERE mentioned_user_id = $1 
						 ORDER BY created_at DESC`,
						[userId]
					);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					if (liveQuery.initialResults?.rows) {
						setMentions(liveQuery.initialResults.rows);
					} else if (liveQuery.rows) {
						setMentions(liveQuery.rows);
					}

					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: ElectricMention[] }) => {
							if (mounted && result.rows) {
								setMentions(result.rows);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch (liveErr) {
				console.error("[useMentionsElectric] Failed to set up live query:", liveErr);
			}
		}

		startSync();

		return () => {
			mounted = false;
			syncKeyRef.current = null;

			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe();
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}
		};
	}, [userId, electricClient]);

	return { mentions, loading, error };
}
