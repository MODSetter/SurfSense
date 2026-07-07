"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { setCurrentThreadMetadataAtom } from "@/atoms/chat/current-thread.atom";
import { syncChatTabAtom } from "@/atoms/tabs/tabs.atom";
import type { ChatVisibility } from "@/lib/chat/thread-persistence";
import { prefetchThreadData } from "./use-thread-queries";

interface ActivateChatThreadInput {
	id: number | null;
	title?: string;
	url?: string;
	workspaceId: number | string;
	visibility?: ChatVisibility;
	hasComments?: boolean;
}

function getWorkspaceId(workspaceId: number | string): number {
	const parsed = typeof workspaceId === "number" ? workspaceId : Number.parseInt(workspaceId, 10);
	return Number.isNaN(parsed) ? 0 : parsed;
}

function getChatUrl(workspaceId: number | string, threadId: number | null): string {
	return threadId
		? `/dashboard/${workspaceId}/new-chat/${threadId}`
		: `/dashboard/${workspaceId}/new-chat`;
}

export function useActivateChatThread() {
	const router = useRouter();
	const queryClient = useQueryClient();
	const syncChatTab = useSetAtom(syncChatTabAtom);
	const setCurrentThreadMetadata = useSetAtom(setCurrentThreadMetadataAtom);

	const prefetchChatThread = useCallback(
		(threadId: number | null | undefined) => {
			if (typeof threadId === "number" && threadId > 0) {
				prefetchThreadData(queryClient, threadId);
			}
		},
		[queryClient]
	);

	const activateChatThread = useCallback(
		({ id, title, url, workspaceId, visibility, hasComments }: ActivateChatThreadInput) => {
			const numericWorkspaceId = getWorkspaceId(workspaceId);
			const chatUrl = url ?? getChatUrl(workspaceId, id);

			syncChatTab({
				chatId: id,
				title: id ? title : (title ?? "New Chat"),
				chatUrl,
				workspaceId: numericWorkspaceId,
				...(visibility !== undefined ? { visibility } : {}),
				...(hasComments !== undefined ? { hasComments } : {}),
			});

			setCurrentThreadMetadata({
				id,
				workspaceId: numericWorkspaceId,
				...(visibility !== undefined ? { visibility } : {}),
				...(hasComments !== undefined ? { hasComments } : {}),
			});

			if (id) {
				prefetchThreadData(queryClient, id);
			}

			router.push(chatUrl);
		},
		[queryClient, router, setCurrentThreadMetadata, syncChatTab]
	);

	return { activateChatThread, prefetchChatThread };
}
