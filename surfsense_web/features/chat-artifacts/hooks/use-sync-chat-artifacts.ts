import type { ThreadMessageLike } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { useEffect, useMemo } from "react";
import { collectArtifacts } from "../lib/collect-artifacts";
import { chatArtifactsAtom } from "../state/artifacts-panel.atom";

/**
 * Keep `chatArtifactsAtom` in sync with the active thread's messages so the
 * right-panel sidebar (rendered in the layout shell, outside the chat runtime)
 * can read the deliverable list. Clears on unmount and on thread switch (a new
 * `messages` array recomputes to the new thread's artifacts).
 */
export function useSyncChatArtifacts(messages: readonly ThreadMessageLike[]): void {
	const setArtifacts = useSetAtom(chatArtifactsAtom);
	const artifacts = useMemo(() => collectArtifacts(messages), [messages]);

	useEffect(() => {
		setArtifacts(artifacts);
	}, [artifacts, setArtifacts]);

	useEffect(() => () => setArtifacts([]), [setArtifacts]);
}
