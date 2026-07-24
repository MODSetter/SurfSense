"use client";

import { useCallback, useSyncExternalStore } from "react";
import { chatStreamStore, type ThreadStreamState } from "./store";

/**
 * Subscribe to the durable streaming state for a given thread.
 *
 * Returns the live ``ThreadStreamState`` while a turn is streaming (or
 * pending re-hydration from the DB), or ``null`` when the thread has no
 * active overlay — in which case the page falls back to its DB-hydrated
 * messages. State lives in the module-level {@link chatStreamStore}, so it
 * survives the chat page unmounting during in-app navigation.
 */
export function useChatStream(threadId: number | null): ThreadStreamState | null {
	const getSnapshot = useCallback(() => chatStreamStore.getSnapshot(threadId), [threadId]);
	return useSyncExternalStore(chatStreamStore.subscribe, getSnapshot, () => null);
}
