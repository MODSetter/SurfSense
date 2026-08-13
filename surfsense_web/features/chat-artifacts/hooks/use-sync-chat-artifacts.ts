import type { ThreadMessageLike } from "@assistant-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo, useRef } from "react";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { artifactListQueryOptions } from "@/features/artifacts/artifact-query";
import type { ArtifactListItem } from "@/features/artifacts/model";
import {
	type ArtifactCandidate,
	collectArtifacts,
	matchesPersistedArtifact,
	mergePersistedArtifacts,
} from "../lib/collect-artifacts";
import { chatArtifactsAtom } from "../state/artifacts-panel.atom";

const RECONCILIATION_POLL_MS = 3_000;
const RECONCILIATION_TIMEOUT_MS = 10 * 60 * 1_000;

function shouldPollForPersistence(
	candidates: readonly ArtifactCandidate[],
	persisted: readonly ArtifactListItem[],
	threadKey: string,
	startedAtByKey: Map<string, number>,
	persistedKeys: Set<string>
): boolean {
	const candidateKeys = new Set(candidates.map((candidate) => `${threadKey}:${candidate.key}`));
	for (const key of persistedKeys) {
		if (!candidateKeys.has(key)) persistedKeys.delete(key);
	}
	for (const candidate of candidates) {
		if (persisted.some((row) => matchesPersistedArtifact(candidate, row))) {
			persistedKeys.add(`${threadKey}:${candidate.key}`);
		}
	}
	const unresolved = candidates.filter(
		(candidate) =>
			candidate.artifactId == null &&
			!persistedKeys.has(`${threadKey}:${candidate.key}`) &&
			!persisted.some((row) => matchesPersistedArtifact(candidate, row))
	);
	const unresolvedKeys = new Set(unresolved.map((candidate) => `${threadKey}:${candidate.key}`));
	for (const key of startedAtByKey.keys()) {
		if (!unresolvedKeys.has(key)) startedAtByKey.delete(key);
	}

	const now = Date.now();
	return unresolved.some((candidate) => {
		const key = `${threadKey}:${candidate.key}`;
		const startedAt = startedAtByKey.get(key) ?? now;
		startedAtByKey.set(key, startedAt);
		return now - startedAt < RECONCILIATION_TIMEOUT_MS;
	});
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
	const persistencePollStartedAt = useRef(new Map<string, number>());
	const persistedKeys = useRef(new Set<string>());
	const canLoadPersisted = thread.id != null && thread.workspaceId != null;
	const { data: persisted = [] } = useQuery({
		...artifactListQueryOptions(thread.workspaceId ?? 0, thread.id),
		enabled: canLoadPersisted,
		// ponytail: legacy media jobs return before Artifact persistence. Poll is
		// bounded; replace it when those jobs publish artifact-list invalidation.
		refetchInterval: (query) =>
			shouldPollForPersistence(
				messageArtifacts,
				query.state.data ?? [],
				String(thread.id),
				persistencePollStartedAt.current,
				persistedKeys.current
			)
				? RECONCILIATION_POLL_MS
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
