import type { ThreadMessageLike } from "@assistant-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo } from "react";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { artifactListQueryOptions } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
import {
	collectArtifacts,
	matchesPersistedArtifact,
	mergePersistedArtifacts,
} from "../lib/collect-artifacts";
import type { ChatArtifact } from "../model/artifact";
import { chatArtifactsAtom } from "../state/artifacts-panel.atom";

function missingPersistedMedia(
	messageArtifacts: readonly ChatArtifact[],
	persisted: readonly ArtifactListItem[]
): boolean {
	return messageArtifacts.some(
		(message) =>
			message.status === "ready" &&
			message.kind !== "file" &&
			!persisted.some((row) => matchesPersistedArtifact(message, row))
	);
}

/**
 * Keep `chatArtifactsAtom` in sync with the active thread's messages so the
 * right-panel sidebar (rendered in the layout shell, outside the chat runtime)
 * can read the deliverable list. Clears on unmount and on thread switch (a new
 * `messages` array recomputes to the new thread's artifacts).
 */
export function useSyncChatArtifacts(messages: readonly ThreadMessageLike[]): void {
	const setArtifacts = useSetAtom(chatArtifactsAtom);
	const thread = useAtomValue(currentThreadAtom);
	const messageArtifacts = useMemo(() => collectArtifacts(messages), [messages]);
	const canLoadPersisted = thread.id != null && thread.workspaceId != null;
	const { data: persisted = [] } = useQuery({
		...artifactListQueryOptions(thread.workspaceId ?? 0, thread.id),
		enabled: canLoadPersisted,
		// Media persistence may finish after its tool result. Poll only
		// during that short reconciliation window so download IDs appear promptly.
		refetchInterval: (query) =>
			query.state.dataUpdateCount < 10 &&
			missingPersistedMedia(messageArtifacts, query.state.data ?? [])
				? 3_000
				: false,
	});
	const artifacts = useMemo(
		() => mergePersistedArtifacts(messageArtifacts, persisted),
		[messageArtifacts, persisted]
	);

	useEffect(() => {
		setArtifacts(artifacts);
	}, [artifacts, setArtifacts]);

	useEffect(() => () => setArtifacts([]), [setArtifacts]);
}
