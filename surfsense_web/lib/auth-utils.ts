/**
 * Authentication utilities for handling token expiration and redirects
 */

const REDIRECT_PATH_KEY = "surfsense_redirect_path";
const BEARER_TOKEN_KEY = "surfsense_bearer_token";
const REFRESH_TOKEN_KEY = "surfsense_refresh_token";

// Flag to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

/**
 * Saves the current path and redirects to login page
 * Call this when a 401 response is received
 */
export function handleUnauthorized(): void {
	if (typeof window === "undefined") return;

	// Save the current path (including search params and hash) for redirect after login
	const currentPath = window.location.pathname + window.location.search + window.location.hash;

	// Don't save auth-related paths
	const excludedPaths = ["/auth", "/auth/callback", "/"];
	if (!excludedPaths.includes(window.location.pathname)) {
		localStorage.setItem(REDIRECT_PATH_KEY, currentPath);
	}

	// Clear both tokens
	localStorage.removeItem(BEARER_TOKEN_KEY);
	localStorage.removeItem(REFRESH_TOKEN_KEY);

	// Redirect to home page (which has login options)
	window.location.href = "/login";
}

/**
 * Gets the stored redirect path and clears it from storage
 * Call this after successful login to redirect the user back
 */
export function getAndClearRedirectPath(): string | null {
	if (typeof window === "undefined") return null;

	const redirectPath = localStorage.getItem(REDIRECT_PATH_KEY);
	if (redirectPath) {
		localStorage.removeItem(REDIRECT_PATH_KEY);
	}
	return redirectPath;
}

/**
 * Gets the bearer token from localStorage
 */
export function getBearerToken(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(BEARER_TOKEN_KEY);
}

/**
 * Sets the bearer token in localStorage
 */
export function setBearerToken(token: string): void {
	if (typeof window === "undefined") return;
	localStorage.setItem(BEARER_TOKEN_KEY, token);
}

/**
 * Clears the bearer token from localStorage
 */
export function clearBearerToken(): void {
	if (typeof window === "undefined") return;
	localStorage.removeItem(BEARER_TOKEN_KEY);
}

/**
 * Gets the refresh token from localStorage
 */
export function getRefreshToken(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Sets the refresh token in localStorage
 */
export function setRefreshToken(token: string): void {
	if (typeof window === "undefined") return;
	localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

/**
 * Clears the refresh token from localStorage
 */
export function clearRefreshToken(): void {
	if (typeof window === "undefined") return;
	localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * Clears all auth tokens from localStorage
 */
export function clearAllTokens(): void {
	clearBearerToken();
	clearRefreshToken();
}

/**
 * Checks if the user is authenticated (has a token)
 */
export function isAuthenticated(): boolean {
	return !!getBearerToken();
}

/**
 * Saves the current path and redirects to login page
 * Use this for client-side auth checks (e.g., in useEffect)
 * Unlike handleUnauthorized, this doesn't clear the token (user might not have one)
 */
export function redirectToLogin(): void {
	if (typeof window === "undefined") return;

	// Save the current path (including search params and hash) for redirect after login
	const currentPath = window.location.pathname + window.location.search + window.location.hash;

	// Don't save auth-related paths or home page
	const excludedPaths = ["/auth", "/auth/callback", "/", "/login", "/register"];
	if (!excludedPaths.includes(window.location.pathname)) {
		localStorage.setItem(REDIRECT_PATH_KEY, currentPath);
	}

	// Redirect to login page
	window.location.href = "/login";
}

/**
 * Creates headers with authorization bearer token
 */
export function getAuthHeaders(additionalHeaders?: Record<string, string>): Record<string, string> {
	const token = getBearerToken();
	return {
		...(token ? { Authorization: `Bearer ${token}` } : {}),
		...additionalHeaders,
	};
}

/**
 * Attempts to refresh the access token using the stored refresh token.
 * Returns the new access token if successful, null otherwise.
 */
async function refreshAccessToken(): Promise<string | null> {
	// If already refreshing, wait for that request to complete
	if (isRefreshing && refreshPromise) {
		return refreshPromise;
	}

	const currentRefreshToken = getRefreshToken();
	if (!currentRefreshToken) {
		return null;
	}

	isRefreshing = true;
	refreshPromise = (async () => {
		try {
			const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
			const response = await fetch(`${backendUrl}/auth/jwt/refresh`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ refresh_token: currentRefreshToken }),
			});

			if (!response.ok) {
				// Refresh failed, clear tokens
				clearAllTokens();
				return null;
			}

			const data = await response.json();
			if (data.access_token && data.refresh_token) {
				setBearerToken(data.access_token);
				setRefreshToken(data.refresh_token);
				return data.access_token;
			}
			return null;
		} catch {
			return null;
		} finally {
			isRefreshing = false;
			refreshPromise = null;
		}
	})();

	return refreshPromise;
}

/**
 * Authenticated fetch wrapper that handles 401 responses uniformly.
 * On 401, attempts to refresh the token and retry the request.
 * If refresh fails, redirects to login and saves the current path.
 */
export async function authenticatedFetch(
	url: string,
	options?: RequestInit & { skipAuthRedirect?: boolean; skipRefresh?: boolean }
): Promise<Response> {
	const { skipAuthRedirect = false, skipRefresh = false, ...fetchOptions } = options || {};

	const headers = getAuthHeaders(fetchOptions.headers as Record<string, string>);

	const response = await fetch(url, {
		...fetchOptions,
		headers,
	});

	// Handle 401 Unauthorized
	if (response.status === 401 && !skipAuthRedirect) {
		// Try to refresh the token (unless skipRefresh is set to prevent infinite loops)
		if (!skipRefresh) {
			const newToken = await refreshAccessToken();
			if (newToken) {
				// Retry the original request with the new token
				const retryHeaders = {
					...(fetchOptions.headers as Record<string, string>),
					Authorization: `Bearer ${newToken}`,
				};
				return fetch(url, {
					...fetchOptions,
					headers: retryHeaders,
				});
			}
		}

		// Refresh failed or was skipped, redirect to login
		handleUnauthorized();
		throw new Error("Unauthorized: Redirecting to login page");
	}

	return response;
}
