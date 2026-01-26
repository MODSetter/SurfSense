"use client";

import { type AppendMessage, useExternalStoreRuntime } from "@assistant-ui/react";
import { useCallback, useMemo } from "react";
import type { GetPublicChatResponse, PublicChatMessage } from "@/contracts/types/public-chat.types";
import { convertToThreadMessage } from "@/lib/chat/message-utils";
import type { MessageRecord } from "@/lib/chat/thread-persistence";

interface UsePublicChatRuntimeOptions {
	data: GetPublicChatResponse | undefined;
}

/**
 * Map PublicChatMessage to MessageRecord shape for reuse of convertToThreadMessage
 */
function toMessageRecord(msg: PublicChatMessage, idx: number): MessageRecord {
	return {
		id: idx,
		thread_id: 0,
		role: msg.role as "user" | "assistant" | "system",
		content: msg.content,
		created_at: msg.created_at,
		author_id: msg.author ? "public" : null,
		author_display_name: msg.author?.display_name ?? null,
		author_avatar_url: msg.author?.avatar_url ?? null,
	};
}

/**
 * Creates a read-only runtime for public chat viewing.
 */
export function usePublicChatRuntime({ data }: UsePublicChatRuntimeOptions) {
	const messages = useMemo(() => data?.messages ?? [], [data?.messages]);

	// No-op - public chat is read-only
	const onNew = useCallback(async (_message: AppendMessage) => {}, []);

	const convertMessage = useCallback(
		(msg: PublicChatMessage, idx: number) => convertToThreadMessage(toMessageRecord(msg, idx)),
		[]
	);

	const runtime = useExternalStoreRuntime({
		isRunning: false,
		messages,
		onNew,
		convertMessage,
	});

	return runtime;
}
