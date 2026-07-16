"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo } from "react";
import { pruneMissingChatTabsAtom, type Tab, tabsAtom } from "@/atoms/tabs/tabs.atom";
import type { ChatVisibility } from "@/lib/chat/thread-persistence";
import { queries } from "@/zero/queries";

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
				tab.entityId === null ? "Document" : (documents.get(tab.entityId)?.title ?? `Document ${tab.entityId}`);
			return { ...tab, title };
		}

		const row = tab.entityId === null ? undefined : threads.get(tab.entityId);
		return {
			...tab,
			title: row?.title || (tab.entityId === null ? "New Chat" : `Chat ${tab.entityId}`),
			chatUrl: getChatUrl(tab.workspaceId, tab.entityId),
			...(row?.visibility !== undefined ? { visibility: row.visibility as ChatVisibility } : {}),
		};
	});
}

export function getMissingCompleteChatIds({
	tabs,
	threadRows,
	resultType,
}: {
	tabs: Tab[];
	threadRows?: readonly ThreadRow[];
	resultType: string;
}): Set<number> {
	if (resultType !== "complete") return new Set();

	const threadIds = new Set((threadRows ?? []).map((row) => row.id));
	return new Set(
		tabs
			.filter(
				(tab): tab is Tab & { type: "chat"; entityId: number } =>
					tab.type === "chat" && tab.entityId !== null && !threadIds.has(tab.entityId)
			)
			.map((tab) => tab.entityId)
	);
}

export function useResolvedTabs(): ResolvedTab[] {
	const tabs = useAtomValue(tabsAtom);
	const pruneMissingChatTabs = useSetAtom(pruneMissingChatTabsAtom);

	const chatIds = useMemo(() => uniqueEntityIds(tabs, "chat"), [tabs]);
	const documentIds = useMemo(() => uniqueEntityIds(tabs, "document"), [tabs]);
	const [threadRows, threadResult] = useQuery(
		queries.threads.byIds({ ids: chatIds.length > 0 ? chatIds : [-1] })
	);
	const [documentRows] = useQuery(
		queries.documents.byIds({ ids: documentIds.length > 0 ? documentIds : [-1] })
	);

	const missingChatIds = useMemo(
		() =>
			getMissingCompleteChatIds({
				tabs,
				threadRows,
				resultType: threadResult.type,
			}),
		[tabs, threadRows, threadResult.type]
	);

	useEffect(() => {
		pruneMissingChatTabs(missingChatIds);
	}, [missingChatIds, pruneMissingChatTabs]);

	return useMemo(
		() => resolveTabPointers({ tabs, threadRows, documentRows }),
		[tabs, threadRows, documentRows]
	);
}
