"use client";

import { useQueries } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo } from "react";
import { pruneMissingChatTabsAtom, type Tab, tabsAtom } from "@/atoms/tabs/tabs.atom";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { type ChatVisibility, getThreadFull } from "@/lib/chat/thread-persistence";
import { NotFoundError } from "@/lib/error";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// Thread/document metadata is read-only for tabs: the DB is the single source
// of truth and react-query is the cache (default staleTime from the shared
// QueryClient). Titles/visibility stay fresh because the rename/visibility/
// delete mutations patch these same query caches (see lib/chat/thread-cache.ts),
// so a rename reflects in the tab bar immediately regardless of staleness.
interface ThreadRow {
	id: number;
	title: string;
	visibility: string;
}

interface DocumentRow {
	id: number;
	title: string;
}

export interface ResolvedTab extends Tab {
	title: string;
	chatUrl?: string;
	visibility?: ChatVisibility;
}

function uniqueEntityIds(tabs: Tab[], type: Tab["type"]): number[] {
	const ids = new Set<number>();
	for (const tab of tabs) {
		if (tab.type === type && tab.entityId !== null) {
			ids.add(tab.entityId);
		}
	}
	return [...ids];
}

function rowById<T extends { id: number }>(rows: readonly T[] | undefined): Map<number, T> {
	return new Map((rows ?? []).map((row) => [row.id, row]));
}

// Retry transient failures (network, 5xx) but never a definitive 404 — a
// missing thread/document is authoritative and should settle immediately so
// the tab can be pruned rather than spun on.
function retryUnlessNotFound(failureCount: number, error: Error): boolean {
	return !(error instanceof NotFoundError) && failureCount < 2;
}

export function getChatUrl(workspaceId: number, threadId: number | null): string {
	return threadId
		? `/dashboard/${workspaceId}/new-chat/${threadId}`
		: `/dashboard/${workspaceId}/new-chat`;
}

export function resolveTabPointers({
	tabs,
	threadRows,
	documentRows,
}: {
	tabs: Tab[];
	threadRows?: readonly ThreadRow[];
	documentRows?: readonly DocumentRow[];
}): ResolvedTab[] {
	const threads = rowById(threadRows);
	const documents = rowById(documentRows);

	return tabs.map((tab) => {
		if (tab.type === "document") {
			const title =
				tab.entityId === null
					? "Document"
					: (documents.get(tab.entityId)?.title ?? `Document ${tab.entityId}`);
			return { ...tab, title };
		}

		const row = tab.entityId === null ? undefined : threads.get(tab.entityId);
		return {
			...tab,
			title: row?.title || "New Chat",
			chatUrl: getChatUrl(tab.workspaceId, tab.entityId),
			...(row?.visibility !== undefined ? { visibility: row.visibility as ChatVisibility } : {}),
		};
	});
}

/**
 * A chat tab is prunable only once its thread metadata fetch has settled as a
 * definitive 404 (thread deleted). Transient network/5xx errors are excluded so
 * an outage never wrongly closes open tabs.
 */
export function getMissingChatIds({
	tabs,
	notFoundIds,
}: {
	tabs: Tab[];
	notFoundIds: Set<number>;
}): Set<number> {
	return new Set(
		tabs
			.filter(
				(tab): tab is Tab & { type: "chat"; entityId: number } =>
					tab.type === "chat" && tab.entityId !== null && notFoundIds.has(tab.entityId)
			)
			.map((tab) => tab.entityId)
	);
}

export function useResolvedTabs(): ResolvedTab[] {
	const tabs = useAtomValue(tabsAtom);
	const pruneMissingChatTabs = useSetAtom(pruneMissingChatTabsAtom);

	const chatIds = useMemo(() => uniqueEntityIds(tabs, "chat"), [tabs]);
	const documentIds = useMemo(() => uniqueEntityIds(tabs, "document"), [tabs]);

	const threadResults = useQueries({
		queries: chatIds.map((id) => ({
			queryKey: cacheKeys.threads.detail(id),
			queryFn: () => getThreadFull(id),
			retry: retryUnlessNotFound,
		})),
	});

	const documentResults = useQueries({
		queries: documentIds.map((id) => ({
			queryKey: cacheKeys.documents.document(String(id)),
			queryFn: () => documentsApiService.getDocument({ id }),
			retry: retryUnlessNotFound,
		})),
	});

	const threadRows: ThreadRow[] = threadResults.flatMap((result, index) =>
		result.data
			? [{ id: chatIds[index], title: result.data.title, visibility: result.data.visibility }]
			: []
	);
	const documentRows: DocumentRow[] = documentResults.flatMap((result, index) =>
		result.data ? [{ id: documentIds[index], title: result.data.title }] : []
	);

	// Stable primitive key of the threads that settled as 404, so the prune
	// effect fires only when that set changes — not on every react-query render.
	const notFoundChatIdsKey = threadResults
		.flatMap((result, index) => (result.error instanceof NotFoundError ? [chatIds[index]] : []))
		.sort((a, b) => a - b)
		.join(",");

	useEffect(() => {
		const notFoundIds = new Set(
			notFoundChatIdsKey ? notFoundChatIdsKey.split(",").map(Number) : []
		);
		const missing = getMissingChatIds({ tabs, notFoundIds });
		if (missing.size > 0) pruneMissingChatTabs(missing);
	}, [notFoundChatIdsKey, tabs, pruneMissingChatTabs]);

	return resolveTabPointers({ tabs, threadRows, documentRows });
}
