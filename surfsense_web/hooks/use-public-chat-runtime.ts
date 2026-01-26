"use client";

import {
	type AppendMessage,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useCallback, useMemo } from "react";
import type { GetPublicChatResponse, PublicChatMessage } from "@/contracts/types/public-chat.types";

interface UsePublicChatRuntimeOptions {
	data: GetPublicChatResponse | undefined;
}

/**
 * Creates a read-only runtime for public chat viewing.
 */
export function usePublicChatRuntime({ data }: UsePublicChatRuntimeOptions) {
	const messages = useMemo(() => data?.messages ?? [], [data?.messages]);

	// No-op - public chat is read-only
	const onNew = useCallback(async (_message: AppendMessage) => {}, []);

	// Convert PublicChatMessage to ThreadMessageLike
	const convertMessage = useCallback(
		(msg: PublicChatMessage, idx: number): ThreadMessageLike => ({
			id: `public-msg-${idx}`,
			role: msg.role as "user" | "assistant",
			content: msg.content as ThreadMessageLike["content"],
			createdAt: new Date(msg.created_at),
			metadata: msg.author
				? {
						custom: {
							author: {
								displayName: msg.author.display_name,
								avatarUrl: msg.author.avatar_url,
							},
						},
					}
				: undefined,
		}),
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
