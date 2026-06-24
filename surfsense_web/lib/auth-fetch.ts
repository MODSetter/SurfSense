import { handleUnauthorized, isDesktopClient, refreshSession } from "@/lib/auth-utils";

let desktopAccessToken: string | null = null;
let didSubscribeToDesktopAuth = false;

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

export async function getDesktopAccessToken(): Promise<string | null> {
	if (!isDesktopClient()) return null;
	subscribeToDesktopAuth();
	if (desktopAccessToken) return desktopAccessToken;
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

export async function authenticatedFetch(
	url: string,
	options?: RequestInit & { skipAuthRedirect?: boolean; skipRefresh?: boolean }
): Promise<Response> {
	const { skipAuthRedirect = false, skipRefresh = false, ...fetchOptions } = options || {};
	const token = await getDesktopAccessToken();
	const headers = {
		...(fetchOptions.headers as Record<string, string>),
		...(token ? { Authorization: `Bearer ${token}` } : {}),
	};

	const response = await fetch(url, {
		...fetchOptions,
		headers,
		credentials: "include",
	});

	if (response.status === 401 && !skipAuthRedirect) {
		if (!skipRefresh) {
			const refreshed = await refreshSession();
			if (refreshed) {
				const newToken = await getDesktopAccessToken();
				return fetch(url, {
					...fetchOptions,
					headers: {
						...(fetchOptions.headers as Record<string, string>),
						...(newToken ? { Authorization: `Bearer ${newToken}` } : {}),
					},
					credentials: "include",
				});
			}
		}

		handleUnauthorized();
		throw new Error("Unauthorized: Redirecting to login page");
	}

	return response;
}
