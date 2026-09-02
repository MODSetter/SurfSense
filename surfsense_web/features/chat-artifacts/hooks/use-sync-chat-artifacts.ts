import type { ThreadMessageLike } from "@assistant-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { useEffect, useMemo, useRef } from "react";
import { artifactListQueryOptions } from "@/features/artifacts/api/artifact-queries";
import type { ArtifactListItem } from "@/features/artifacts/model/artifact";
import {
	type ArtifactCandidate,
	collectArtifacts,
	matchesPersistedArtifact,
	resolveArtifactRowsWithLegacyCompatibility,
} from "../lib/collect-artifacts";
import type { ChatArtifact } from "../model/artifact";
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
export function useSyncChatArtifacts(
	messages: readonly ThreadMessageLike[],
	threadId: number | null,
	workspaceId: number
): {
	artifacts: ChatArtifact[];
	isReady: boolean;
} {
	const setArtifacts = useSetAtom(chatArtifactsAtom);
	const messageArtifacts = useMemo(() => collectArtifacts(messages), [messages]);
	const persistencePollStartedAt = useRef(new Map<string, number>());
	const persistedKeys = useRef(new Set<string>());
	const canLoadPersisted = threadId != null && workspaceId > 0;
	const {
		data: persisted = [],
		isError,
		isPending,
	} = useQuery({
		...artifactListQueryOptions(workspaceId, threadId),
		enabled: canLoadPersisted,
		// ponytail: legacy media jobs return before Artifact persistence. Poll is
		// bounded; replace it when those jobs publish artifact-list invalidation.
		refetchInterval: (query) =>
			shouldPollForPersistence(
				messageArtifacts,
				query.state.data ?? [],
				String(threadId),
				persistencePollStartedAt.current,
				persistedKeys.current
			)
				? RECONCILIATION_POLL_MS
				: false,
	});
	const artifacts = useMemo(
		() => resolveArtifactRowsWithLegacyCompatibility(messageArtifacts, persisted),
		[messageArtifacts, persisted]
	);

	useEffect(() => {
		setArtifacts(artifacts);
	}, [artifacts, setArtifacts]);

	useEffect(() => () => setArtifacts([]), [setArtifacts]);

	// Compatibility layer: a failed persisted-metadata read must not make deep
	// links discard historical artifacts. React Query can retry on focus.
	return {
		artifacts,
		isReady: !canLoadPersisted || (!isPending && !isError),
	};
}
