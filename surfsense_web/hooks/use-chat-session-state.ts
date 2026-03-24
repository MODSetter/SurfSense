"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useSetAtom } from "jotai";
import { useEffect } from "react";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import { queries } from "@/zero/queries";

/**
 * Syncs chat session state for a thread via Zero.
 * Call once per thread (in page.tsx). Updates global atom.
 */
export function useChatSessionStateSync(threadId: number | null) {
	const setSessionState = useSetAtom(chatSessionStateAtom);

	const [row] = useQuery(queries.chatSession.byThread({ threadId: threadId ?? -1 }));

	useEffect(() => {
		if (!threadId) {
			setSessionState(null);
			return;
		}

		setSessionState({
			threadId,
			isAiResponding: !!row?.aiRespondingToUserId,
			respondingToUserId: row?.aiRespondingToUserId ?? null,
		});
	}, [threadId, row, setSessionState]);
}
