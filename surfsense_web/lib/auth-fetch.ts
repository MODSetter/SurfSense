import { handleUnauthorized, isDesktopClient, refreshSession } from "@/lib/auth-utils";

let desktopAccessToken: string | null = null;
let didSubscribeToDesktopAuth = false;

type DesktopAccessTokenOptions = {
	forceRefresh?: boolean;
};

type AuthenticatedFetchOptions = RequestInit & {
	skipAuthRedirect?: boolean;
	skipRefresh?: boolean;
	forceDesktopTokenRefresh?: boolean;
};

function subscribeToDesktopAuth(): void {
	if (didSubscribeToDesktopAuth || typeof window === "undefined" || !window.electronAPI) {
		return;
	}
	didSubscribeToDesktopAuth = true;

	window.electronAPI.onAuthChanged?.(({ accessToken }) => {
		desktopAccessToken = accessToken;
	});
	void window.electronAPI.getAccessToken?.().then((token) => {
		if (token) desktopAccessToken = token;
	});
}

export async function getDesktopAccessToken(
	options: DesktopAccessTokenOptions = {}
): Promise<string | null> {
	if (!isDesktopClient()) return null;
	subscribeToDesktopAuth();
	if (desktopAccessToken && !options.forceRefresh) return desktopAccessToken;
	const token = (await window.electronAPI?.getAccessToken?.()) || null;
	desktopAccessToken = token;
	return token;
}

export function getAuthHeaders(additionalHeaders?: Record<string, string>): Record<string, string> {
	subscribeToDesktopAuth();
	return {
		...(desktopAccessToken ? { Authorization: `Bearer ${desktopAccessToken}` } : {}),
		...additionalHeaders,
	};
}

async function fetchWithAuth(
	url: string,
	options: RequestInit,
	{ forceDesktopTokenRefresh = false }: { forceDesktopTokenRefresh?: boolean } = {}
): Promise<Response> {
	const headers = new Headers(options.headers);
	const token = await getDesktopAccessToken({ forceRefresh: forceDesktopTokenRefresh });
	if (token) {
		headers.set("Authorization", `Bearer ${token}`);
	}

	return fetch(url, {
		...options,
		headers,
		credentials: options.credentials ?? "include",
	});
}

export async function authenticatedFetch(
	url: string,
	options: AuthenticatedFetchOptions = {}
): Promise<Response> {
	const {
		skipAuthRedirect = false,
		skipRefresh = false,
		forceDesktopTokenRefresh = false,
		...fetchOptions
	} = options;

	const response = await fetchWithAuth(url, fetchOptions, {
		forceDesktopTokenRefresh,
	});

	if (response.status !== 401) {
		return response;
	}

	let unauthorizedResponse = response;
	if (!skipRefresh) {
		const refreshed = await refreshSession();
		if (refreshed) {
			const retryResponse = await fetchWithAuth(url, fetchOptions, {
				forceDesktopTokenRefresh: true,
			});
			if (retryResponse.status !== 401) {
				return retryResponse;
			}
			unauthorizedResponse = retryResponse;
		}
	}

	if (!skipAuthRedirect) {
		handleUnauthorized();
		throw new Error("Unauthorized: Redirecting to login page");
	}

	return unauthorizedResponse;
}
