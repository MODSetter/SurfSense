"use client";

import { type QueryClient, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef } from "react";
import {
	type AgentAction,
	type AgentActionListResponse,
	agentActionsApiService,
} from "@/lib/apis/agent-actions-api.service";

// =============================================================================
// DIAGNOSTIC LOGGING — gated behind a single switch. Flip ``RevertDebug``
// to ``true`` to trace the full SSE → cache → card → button pipeline in
// the browser console. Off by default so we don't spam production. The
// infrastructure stays in place because the underlying id-mismatch
// failure mode is rare-but-real and surfaces only at runtime.
// =============================================================================
const RevertDebug = false;
const dbg = (...args: unknown[]) => {
	if (RevertDebug && typeof window !== "undefined") {
		// eslint-disable-next-line no-console
		console.log("[RevertDebug]", ...args);
	}
};

/**
 * Unified store for ``AgentActionLog`` rows scoped to one thread.
 *
 * Replaces the previous SSE side-channel atom mess
 * (``agentActionByLcIdAtom`` / ``agentActionByToolCallIdAtom`` /
 * ``agentActionsByChatTurnIdAtom``) and the standalone hydration hook.
 * One react-query cache entry is now the single source of truth for:
 *
 * * the inline Revert button on every tool-call card
 * * the per-turn "Revert turn" button under each assistant message
 * * the edit-from-position pre-flight that decides whether to show
 *   the confirmation dialog
 * * the agent-actions sheet
 *
 * The cache is hydrated by ``GET /threads/{id}/actions`` (sized to
 * 200, the server max) and updated incrementally by helpers that turn
 * SSE events / revert RPC responses into ``setQueryData`` mutations.
 * That keeps the card and the sheet in lockstep on every code path —
 * page reload, navigation, live stream, post-stream reversibility flip,
 * and explicit revert clicks.
 */

export const ACTION_LOG_PAGE_SIZE = 200;

/** Stable react-query key for the per-thread action list. */
export function agentActionsQueryKey(threadId: number | null) {
	return threadId !== null
		? (["agent-actions", threadId] as const)
		: (["agent-actions", "none"] as const);
}

/** Subset of the SSE ``data-action-log`` payload we care about. */
export interface ActionLogSseEvent {
	id: number;
	lc_tool_call_id: string | null;
	chat_turn_id: string | null;
	tool_name: string;
	reversible: boolean;
	reverse_descriptor_present: boolean;
	error: boolean;
	created_at: string | null;
}

/**
 * Append or upsert a freshly-emitted ``AgentActionLog`` row into the
 * thread-scoped query cache.
 *
 * The SSE payload is a strict subset of ``AgentAction``; missing
 * fields (``args``, ``reverse_descriptor``, ``user_id``) are filled
 * with ``null`` placeholders. The next refetch (sheet open, user
 * focus, route stale) backfills them — but the inline Revert button
 * only reads the fields the SSE payload carries, so it lights up
 * immediately.
 */
export function applyActionLogSse(
	queryClient: QueryClient,
	threadId: number,
	searchSpaceId: number,
	event: ActionLogSseEvent
): void {
	dbg("applyActionLogSse: incoming SSE event", {
		threadId,
		searchSpaceId,
		event,
	});
	queryClient.setQueryData<AgentActionListResponse>(agentActionsQueryKey(threadId), (prev) => {
		const placeholder: AgentAction = {
			id: event.id,
			thread_id: threadId,
			user_id: null,
			search_space_id: searchSpaceId,
			tool_name: event.tool_name,
			args: null,
			result_id: null,
			reversible: event.reversible,
			reverse_descriptor: event.reverse_descriptor_present ? {} : null,
			error: event.error ? {} : null,
			reverse_of: null,
			reverted_by_action_id: null,
			is_revert_action: false,
			tool_call_id: event.lc_tool_call_id,
			chat_turn_id: event.chat_turn_id,
			created_at: event.created_at ?? new Date().toISOString(),
		};
		if (!prev) {
			return {
				items: [placeholder],
				total: 1,
				page: 0,
				page_size: ACTION_LOG_PAGE_SIZE,
				has_more: false,
			};
		}
		const existingIdx = prev.items.findIndex((a) => a.id === event.id);
		if (existingIdx >= 0) {
			const merged = [...prev.items];
			const existing = merged[existingIdx];
			if (existing) {
				merged[existingIdx] = {
					...existing,
					reversible: event.reversible,
					tool_call_id: event.lc_tool_call_id ?? existing.tool_call_id,
					chat_turn_id: event.chat_turn_id ?? existing.chat_turn_id,
				};
			}
			dbg("applyActionLogSse: merged into existing entry", {
				id: event.id,
				tool_call_id: merged[existingIdx]?.tool_call_id,
				reversible: merged[existingIdx]?.reversible,
			});
			return { ...prev, items: merged };
		}
		dbg("applyActionLogSse: appended new placeholder", {
			id: event.id,
			tool_call_id: placeholder.tool_call_id,
			tool_name: placeholder.tool_name,
			reversible: placeholder.reversible,
			cacheSizeAfter: prev.items.length + 1,
		});
		// REST returns newest-first — keep that ordering when
		// the server eventually refetches by prepending.
		return {
			...prev,
			items: [placeholder, ...prev.items],
			total: prev.total + 1,
		};
	});
}

/**
 * Apply a post-SAVEPOINT reversibility flip
 * (``data-action-log-updated`` SSE event) to the cache.
 */
export function applyActionLogUpdatedSse(
	queryClient: QueryClient,
	threadId: number,
	id: number,
	reversible: boolean
): void {
	dbg("applyActionLogUpdatedSse: reversibility flip", {
		threadId,
		id,
		reversible,
	});
	queryClient.setQueryData<AgentActionListResponse>(agentActionsQueryKey(threadId), (prev) => {
		if (!prev) {
			dbg("applyActionLogUpdatedSse: NO prev cache for thread; flip dropped", {
				threadId,
				id,
			});
			return prev;
		}
		let mutated = false;
		const items = prev.items.map((a) => {
			if (a.id !== id) return a;
			mutated = true;
			return { ...a, reversible };
		});
		if (!mutated) {
			dbg("applyActionLogUpdatedSse: id not in cache; flip dropped", {
				threadId,
				id,
				cacheSize: prev.items.length,
				cacheIds: prev.items.map((a) => a.id),
			});
		}
		return mutated ? { ...prev, items } : prev;
	});
}

/**
 * Optimistically mark ``id`` as reverted.
 *
 * Used by the inline / per-turn Revert button immediately after the
 * server returns success so the UI flips to "Reverted" without
 * waiting for a refetch. ``newActionId`` is the id of the new
 * ``is_revert_action`` row the server inserted; pass ``null`` if the
 * server didn't return it.
 */
export function markActionRevertedInCache(
	queryClient: QueryClient,
	threadId: number,
	id: number,
	newActionId: number | null
): void {
	queryClient.setQueryData<AgentActionListResponse>(agentActionsQueryKey(threadId), (prev) => {
		if (!prev) return prev;
		let mutated = false;
		const items = prev.items.map((a) => {
			if (a.id !== id) return a;
			mutated = true;
			// ``-1`` is a sentinel meaning "we know it was reverted
			// but the server didn't tell us the new row's id".
			return {
				...a,
				reverted_by_action_id: newActionId ?? -1,
			};
		});
		return mutated ? { ...prev, items } : prev;
	});
}

/**
 * Apply a batch of revert results (per-turn revert response) to the
 * cache. Anything in the ``reverted`` / ``already_reverted`` buckets
 * gets its ``reverted_by_action_id`` set; other rows are left alone.
 */
export function applyRevertTurnResultsToCache(
	queryClient: QueryClient,
	threadId: number,
	entries: Array<{ id: number; newActionId: number | null }>
): void {
	if (entries.length === 0) return;
	queryClient.setQueryData<AgentActionListResponse>(agentActionsQueryKey(threadId), (prev) => {
		if (!prev) return prev;
		const lookup = new Map(entries.map((e) => [e.id, e.newActionId]));
		let mutated = false;
		const items = prev.items.map((a) => {
			if (!lookup.has(a.id)) return a;
			mutated = true;
			const newActionId = lookup.get(a.id) ?? null;
			return { ...a, reverted_by_action_id: newActionId ?? -1 };
		});
		return mutated ? { ...prev, items } : prev;
	});
}

/**
 * Read-side hook used by the card, the turn button, the sheet, and
 * the edit-from-position pre-flight.
 *
 * Returns the raw query state plus convenience selectors so consumers
 * don't reach into ``data.items`` directly. ``enabled`` is the only
 * knob — pass ``false`` to keep the query dormant when the consumer
 * doesn't yet have a thread id.
 */
export function useAgentActionsQuery(threadId: number | null, options: { enabled?: boolean } = {}) {
	const enabled = (options.enabled ?? true) && threadId !== null;
	const query = useQuery({
		queryKey: agentActionsQueryKey(threadId),
		queryFn: async () => {
			dbg("useAgentActionsQuery: REST fetch START", {
				threadId,
				pageSize: ACTION_LOG_PAGE_SIZE,
			});
			const res = await agentActionsApiService.listForThread(threadId as number, {
				page: 0,
				pageSize: ACTION_LOG_PAGE_SIZE,
			});
			dbg("useAgentActionsQuery: REST fetch DONE", {
				threadId,
				total: res.total,
				returned: res.items.length,
				items: res.items.map((a) => ({
					id: a.id,
					tool_name: a.tool_name,
					tool_call_id: a.tool_call_id,
					reversible: a.reversible,
					reverted_by_action_id: a.reverted_by_action_id,
					is_revert_action: a.is_revert_action,
				})),
			});
			return res;
		},
		enabled,
		staleTime: 15 * 1000,
	});

	const items = useMemo(() => query.data?.items ?? [], [query.data]);

	// Index ``items`` once per change so the lookups below are O(1)
	// instead of O(N) per card per render. With the cache sized to 200
	// rows and many tool cards visible at once, the unindexed scan was
	// the hottest path on every assistant text-delta. (Vercel React
	// rule ``js-index-maps`` / ``js-set-map-lookups``.)
	const byToolCallId = useMemo(() => {
		const m = new Map<string, AgentAction>();
		for (const a of items) {
			if (a.tool_call_id) m.set(a.tool_call_id, a);
		}
		return m;
	}, [items]);

	// Pre-grouped + pre-sorted (oldest-first, the order the agent
	// actually executed them in) so the (chat_turn_id, tool_name,
	// position) fallback in ``tool-fallback.tsx`` is also O(1) per
	// card. Excludes ``is_revert_action`` rows so the position index
	// matches the agent's original execution order.
	const byTurnAndTool = useMemo(() => {
		const m = new Map<string, AgentAction[]>();
		for (const a of items) {
			if (!a.chat_turn_id || a.is_revert_action) continue;
			const key = `${a.chat_turn_id}::${a.tool_name}`;
			const bucket = m.get(key);
			if (bucket) bucket.push(a);
			else m.set(key, [a]);
		}
		for (const bucket of m.values()) {
			bucket.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
		}
		return m;
	}, [items]);

	// Snapshot the cache shape when its size changes — easiest way to
	// spot when the cache is empty or stale at the moment a card
	// mounts. Tracked on a ref so we don't re-run the diff on
	// reference-equal cache reads.
	const lastSnapshotRef = useRef<{ threadId: number | null; size: number } | null>(null);
	useEffect(() => {
		const last = lastSnapshotRef.current;
		if (!last || last.threadId !== threadId || last.size !== items.length) {
			dbg("useAgentActionsQuery: cache snapshot", {
				threadId,
				enabled,
				itemCount: items.length,
				itemKeys: items.slice(0, 8).map((a) => ({
					id: a.id,
					tool_name: a.tool_name,
					tool_call_id: a.tool_call_id,
					chat_turn_id: a.chat_turn_id,
					reversible: a.reversible,
				})),
			});
			lastSnapshotRef.current = { threadId, size: items.length };
		}
	}, [threadId, enabled, items]);

	const findByToolCallId = useCallback(
		(toolCallId: string | null | undefined): AgentAction | null => {
			if (!toolCallId) return null;
			const found = byToolCallId.get(toolCallId) ?? null;
			if (!found && items.length > 0) {
				dbg("findByToolCallId: MISS", {
					queriedToolCallId: toolCallId,
					itemCount: items.length,
					availableToolCallIds: Array.from(byToolCallId.keys()),
				});
			}
			return found;
		},
		[byToolCallId, items.length]
	);

	const findByChatTurnId = useCallback(
		(chatTurnId: string | null | undefined): AgentAction[] => {
			if (!chatTurnId) return [];
			// Per-turn aggregation is uncommon enough (only the
			// "Revert turn" button uses it) that re-scanning is fine;
			// indexing it would just bloat memory.
			return items.filter((a) => a.chat_turn_id === chatTurnId);
		},
		[items]
	);

	const findByChatTurnAndTool = useCallback(
		(chatTurnId: string | null | undefined, toolName: string | null | undefined): AgentAction[] => {
			if (!chatTurnId || !toolName) return [];
			return byTurnAndTool.get(`${chatTurnId}::${toolName}`) ?? [];
		},
		[byTurnAndTool]
	);

	return {
		...query,
		items,
		findByToolCallId,
		findByChatTurnId,
		findByChatTurnAndTool,
	};
}
