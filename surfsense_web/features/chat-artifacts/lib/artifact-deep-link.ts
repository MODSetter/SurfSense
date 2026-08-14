export const ARTIFACT_QUERY_PARAM = "artifactId";

export function artifactChatHref(
	workspaceId: number,
	threadId: number | null | undefined,
	artifactId?: number
): string | null {
	if (!Number.isSafeInteger(threadId) || (threadId ?? 0) <= 0) return null;

	const pathname = `/dashboard/${workspaceId}/new-chat/${threadId}`;
	if (!Number.isSafeInteger(artifactId) || (artifactId ?? 0) <= 0) return pathname;

	return `${pathname}?${new URLSearchParams({
		[ARTIFACT_QUERY_PARAM]: String(artifactId),
	})}`;
}

export function artifactIdFromSearch(search: string): number | null {
	const raw = new URLSearchParams(search).get(ARTIFACT_QUERY_PARAM);
	if (!raw) return null;

	const artifactId = Number(raw);
	return Number.isSafeInteger(artifactId) && artifactId > 0 ? artifactId : null;
}
