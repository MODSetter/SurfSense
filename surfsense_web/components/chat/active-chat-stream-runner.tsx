"use client";

import { useEffect } from "react";
import { chatStreamStore } from "@/lib/chat/stream-engine/store";

/**
 * Persistent, render-null host that scopes the in-flight chat turn's lifetime
 * to the workspace shell, not the chat page.
 *
 * Mounted in ``LayoutDataProvider``, it survives in-app navigation between
 * workspace routes and aborts the single active turn only on workspace/app
 * teardown, so ordinary navigation disconnects the view without stopping the
 * stream.
 */
export function ActiveChatStreamRunner() {
	useEffect(() => {
		return () => {
			chatStreamStore.abortActive();
		};
	}, []);

	return null;
}
