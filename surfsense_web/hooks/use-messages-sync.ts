"use client";

import { useEffect, useRef } from "react";
import type { RawMessage } from "@/contracts/types/chat-messages.types";
import { queries } from "@/zero/queries";
import { useQuery } from "@rocicorp/zero/react";

/**
 * Syncs chat messages for a thread via Zero.
 * Calls onMessagesUpdate when messages change.
 */
export function useMessagesSync(
	threadId: number | null,
	onMessagesUpdate: (messages: RawMessage[]) => void
) {
	const onMessagesUpdateRef = useRef(onMessagesUpdate);

	useEffect(() => {
		onMessagesUpdateRef.current = onMessagesUpdate;
	}, [onMessagesUpdate]);

	const [messages] = useQuery(queries.messages.byThread({ threadId: threadId ?? -1 }));

	useEffect(() => {
		if (!threadId || !messages) return;

		const mapped: RawMessage[] = messages.map((msg) => ({
			id: msg.id,
			thread_id: msg.threadId,
			role: msg.role,
			content: msg.content,
			author_id: msg.authorId ?? null,
			created_at: String(msg.createdAt),
		}));

		onMessagesUpdateRef.current(mapped);
	}, [threadId, messages]);
}
