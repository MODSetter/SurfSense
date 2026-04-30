"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useEffect, useRef } from "react";
import type { RawMessage } from "@/contracts/types/chat-messages.types";
import { queries } from "@/zero/queries";

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
			created_at: new Date(msg.createdAt).toISOString(),
			// Forward the per-turn correlation id so post-stream Zero
			// re-syncs preserve ``metadata.custom.chatTurnId`` on the
			// converted ``ThreadMessageLike``. Without this the inline
			// Revert button's ``(chat_turn_id, tool_name, position)``
			// fallback breaks the moment Zero overwrites the messages
			// state after a live stream completes (see
			// ``handleSyncedMessagesUpdate`` in the chat page).
			turn_id: msg.turnId ?? null,
		}));

		onMessagesUpdateRef.current(mapped);
	}, [threadId, messages]);
}
