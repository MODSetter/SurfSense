"use client";

import { useShape } from "@electric-sql/react";
import type { ChatSessionState } from "@/contracts/types/chat-session-state.types";

const ELECTRIC_URL = process.env.NEXT_PUBLIC_ELECTRIC_URL || "http://localhost:5133";

export function useChatSessionState(threadId: number | null) {
	const { data, isLoading, isError, error } = useShape<ChatSessionState>({
		url: `${ELECTRIC_URL}/v1/shape`,
		params: {
			table: "chat_session_state",
			where: `thread_id = ${threadId}`,
		},
		// Skip fetching if no threadId
		...(threadId ? {} : { url: undefined as unknown as string }),
	});

	const sessionState = data?.[0] ?? null;

	return {
		sessionState,
		isAiResponding: !!sessionState?.ai_responding_to_user_id,
		respondingToUserId: sessionState?.ai_responding_to_user_id ?? null,
		loading: isLoading,
		error: isError ? error : null,
	};
}
