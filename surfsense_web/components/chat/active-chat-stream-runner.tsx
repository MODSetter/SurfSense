"use client";

import { useEffect } from "react";
import { chatStreamStore } from "@/lib/chat/stream-engine/store";

/**
 * Persistent, render-null host for app-wide chat-stream lifecycle.
 *
 * Mounted in the workspace shell (``LayoutDataProvider``), it persists across
 * in-app navigation between workspace routes (``/new-chat`` -> ``/chats`` ->
 * ``/automations`` and doc-tab switches) and only unmounts on real teardown
 * (workspace change / app teardown). On that teardown it aborts the single
 * in-flight turn — this replaces the old chat-page unmount abort, which was
 * what killed streams on ordinary navigation.
 *
 * NOTE: the ``hitl-decision`` bridge and ``useChatSessionStateSync`` stay in
 * the chat page: both need the currently-viewed thread id (HITL resume can
 * only be triggered from the page's approval UI), which the shell-level runner
 * does not cleanly have.
 */
export function ActiveChatStreamRunner() {
	useEffect(() => {
		return () => {
			chatStreamStore.abortActive();
		};
	}, []);

	return null;
}
