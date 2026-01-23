"use client";

import { useCallback, useEffect, useRef } from "react";
import type { RawMessage } from "@/contracts/types/chat-messages.types";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

/**
 * Syncs chat messages for a thread via Electric SQL.
 * Calls onMessagesUpdate when messages change.
 */
export function useMessagesElectric(
	threadId: number | null,
	onMessagesUpdate: (messages: RawMessage[]) => void
) {
	const electricClient = useElectricClient();

	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const syncKeyRef = useRef<string | null>(null);
	const onMessagesUpdateRef = useRef(onMessagesUpdate);

	useEffect(() => {
		onMessagesUpdateRef.current = onMessagesUpdate;
	}, [onMessagesUpdate]);

	const handleMessagesUpdate = useCallback((rows: RawMessage[]) => {
		onMessagesUpdateRef.current(rows);
	}, []);

	useEffect(() => {
		if (!threadId || !electricClient) {
			return;
		}

		const syncKey = `messages_${threadId}`;
		if (syncKeyRef.current === syncKey) {
			return;
		}

		const client = electricClient;
		let mounted = true;
		syncKeyRef.current = syncKey;

		async function startSync() {
			try {
				const handle = await client.syncShape({
					table: "new_chat_messages",
					where: `thread_id = ${threadId}`,
					columns: ["id", "thread_id", "role", "content", "author_id", "created_at"],
					primaryKey: ["id"],
				});

				if (!handle.isUpToDate && handle.initialSyncPromise) {
					try {
						await Promise.race([
							handle.initialSyncPromise,
							new Promise((resolve) => setTimeout(resolve, 3000)),
						]);
					} catch {
						// Timeout
					}
				}

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				await fetchMessages();
				await setupLiveQuery();
			} catch {
				// Sync failed
			}
		}

		async function fetchMessages() {
			try {
				const result = await client.db.query<RawMessage>(
					`SELECT id, thread_id, role, content, author_id, created_at 
					 FROM new_chat_messages 
					 WHERE thread_id = $1 
					 ORDER BY created_at ASC`,
					[threadId]
				);

				if (mounted && result.rows) {
					handleMessagesUpdate(result.rows);
				}
			} catch {
				// Query failed
			}
		}

		async function setupLiveQuery() {
			try {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = client.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(
						`SELECT id, thread_id, role, content, author_id, created_at 
						 FROM new_chat_messages 
						 WHERE thread_id = $1 
						 ORDER BY created_at ASC`,
						[threadId]
					);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					if (liveQuery.initialResults?.rows) {
						handleMessagesUpdate(liveQuery.initialResults.rows);
					} else if (liveQuery.rows) {
						handleMessagesUpdate(liveQuery.rows);
					}

					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: RawMessage[] }) => {
							if (mounted && result.rows) {
								handleMessagesUpdate(result.rows);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch {
				// Live query failed
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
	}, [threadId, electricClient, handleMessagesUpdate]);
}
