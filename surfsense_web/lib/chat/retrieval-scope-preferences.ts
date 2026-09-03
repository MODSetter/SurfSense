import {
	DEFAULT_RETRIEVAL_SCOPE,
	isRetrievalScope,
	type RetrievalScope,
} from "@/contracts/types/retrieval-scope.types";

export const RETRIEVAL_SCOPE_COOKIE = "surfsense_retrieval_scope_v1";
export const RETRIEVAL_SCOPE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function parseRetrievalScopeCookie(
	value: string | undefined,
	expectedUserId?: string
): RetrievalScope {
	if (!value) return DEFAULT_RETRIEVAL_SCOPE;
	try {
		const [userId, scope] = decodeURIComponent(value).split(":");
		if (expectedUserId && userId !== expectedUserId) return DEFAULT_RETRIEVAL_SCOPE;
		return isRetrievalScope(scope) ? scope : DEFAULT_RETRIEVAL_SCOPE;
	} catch {
		return DEFAULT_RETRIEVAL_SCOPE;
	}
}

export function persistRetrievalScopeCookie(
	userId: string | undefined,
	workspaceId: number,
	scope: RetrievalScope
): void {
	if (typeof document === "undefined" || !userId) return;
	try {
		const value = encodeURIComponent(`${userId}:${scope}`);
		// biome-ignore lint/suspicious/noDocumentCookie: Cookie Store is not consistently available.
		document.cookie = `${RETRIEVAL_SCOPE_COOKIE}=${value}; path=/dashboard/${workspaceId}; max-age=${RETRIEVAL_SCOPE_COOKIE_MAX_AGE}; samesite=lax`;
	} catch {
		// The in-memory preference still works when browser cookies are disabled.
	}
}
