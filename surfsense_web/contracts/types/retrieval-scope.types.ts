export const RETRIEVAL_SCOPES = ["documents", "web", "all"] as const;

export type RetrievalScope = (typeof RETRIEVAL_SCOPES)[number];

export const DEFAULT_RETRIEVAL_SCOPE: RetrievalScope = "documents";

export function isRetrievalScope(value: unknown): value is RetrievalScope {
	return typeof value === "string" && RETRIEVAL_SCOPES.includes(value as RetrievalScope);
}

export function scopeForMentionKinds(
	scope: RetrievalScope,
	kinds: readonly string[]
): RetrievalScope {
	const requiresDocuments = kinds.some((kind) => kind !== "connector");
	const requiresWeb = kinds.some((kind) => kind === "connector");
	return (scope === "documents" && requiresWeb) || (scope === "web" && requiresDocuments)
		? "all"
		: scope;
}
