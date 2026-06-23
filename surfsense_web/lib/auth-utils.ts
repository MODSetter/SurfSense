/**
 * Authentication utilities for handling token expiration and redirects
 */
import { buildBackendUrl } from "@/lib/env-config";

const REDIRECT_PATH_KEY = "surfsense_redirect_path";
const BEARER_TOKEN_KEY = "surfsense_bearer_token";
const REFRESH_TOKEN_KEY = "surfsense_refresh_token";

let desktopBearerToken: string | null = null;
let desktopRefreshToken: string | null = null;

function isDesktopClient(): boolean {
	return typeof window !== "undefined" && !!window.electronAPI;
}

function purgeLegacyStoredTokens(): void {
	if (typeof window === "undefined") return;
	localStorage.removeItem(BEARER_TOKEN_KEY);
	localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/** Path prefixes for routes that do not require auth (no current-user fetch, no redirect on 401) */
const PUBLIC_ROUTE_PREFIXES = [
	"/login",
	"/register",
	"/auth",
	"/desktop/login",
	"/docs",
	"/public",
	"/free",
	"/invite",
	"/contact",
	"/pricing",
	"/privacy",
	"/terms",
	"/changelog",
];

/**
 * Returns true if the pathname is a public route where we should not run auth checks
 * or redirect to login on 401.
 */
export function isPublicRoute(pathname: string): boolean {
	if (pathname === "/" || pathname === "") return true;
	return PUBLIC_ROUTE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function getLoginPath(): string {
	if (typeof window !== "undefined" && window.electronAPI) return "/desktop/login";
	return "/login";
}

/**
 * Clears tokens and optionally redirects to login.
 * Call this when a 401 response is received.
 * Only redirects when the current route is protected; on public routes we just clear tokens.
 */
export function handleUnauthorized(): void {
	if (typeof window === "undefined") return;

	const pathname = window.location.pathname;

	// Always clear tokens
	purgeLegacyStoredTokens();
	desktopBearerToken = null;
	desktopRefreshToken = null;

	// Only redirect on protected routes; stay on public pages (e.g. /docs)
	if (!isPublicRoute(pathname)) {
		const currentPath = pathname + window.location.search + window.location.hash;
		const excludedPaths = ["/auth", "/auth/callback", "/"];
		if (!excludedPaths.includes(pathname)) {
			setRedirectPath(currentPath);
		}
		window.location.href = getLoginPath();
	}
}

/**
 * Stores the path to redirect to after successful authentication.
 */
export function setRedirectPath(path: string): void {
	if (typeof window === "undefined") return;
	localStorage.setItem(REDIRECT_PATH_KEY, path);
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
	if (typeof window === "undefined" || !isDesktopClient()) return null;
	return desktopBearerToken;
}

/**
 * Sets the bearer token in localStorage
 */
export function setBearerToken(token: string): void {
	if (typeof window === "undefined") return;
	purgeLegacyStoredTokens();
	desktopBearerToken = isDesktopClient() ? token : null;
	syncTokensToElectron();
}

/**
 * Clears the bearer token from localStorage
 */
export function clearBearerToken(): void {
	if (typeof window === "undefined") return;
	localStorage.removeItem(BEARER_TOKEN_KEY);
	desktopBearerToken = null;
}

/**
 * Gets the refresh token from localStorage
 */
export function getRefreshToken(): string | null {
	if (typeof window === "undefined" || !isDesktopClient()) return null;
	return desktopRefreshToken;
}

/**
 * Sets the refresh token in localStorage
 */
export function setRefreshToken(token: string): void {
	if (typeof window === "undefined") return;
	purgeLegacyStoredTokens();
	desktopRefreshToken = isDesktopClient() ? token : null;
	syncTokensToElectron();
}

/**
 * Clears the refresh token from localStorage
 */
export function clearRefreshToken(): void {
	if (typeof window === "undefined") return;
	localStorage.removeItem(REFRESH_TOKEN_KEY);
	desktopRefreshToken = null;
}

/**
 * Clears all auth tokens from localStorage
 */
export function clearAllTokens(): void {
	clearBearerToken();
	clearRefreshToken();
}

/**
 * Pushes the current localStorage tokens into the Electron main process
 * so that other BrowserWindows (Quick Ask, Autocomplete) can access them.
 */
function syncTokensToElectron(): void {
	if (typeof window === "undefined" || !window.electronAPI?.setAuthTokens) return;
	const bearer = desktopBearerToken || "";
	const refresh = desktopRefreshToken || "";
	if (bearer) {
		window.electronAPI.setAuthTokens(bearer, refresh);
	}
}

/**
 * Attempts to pull auth tokens from the Electron main process into localStorage.
 * Useful for popup windows (Quick Ask, Autocomplete) on platforms where
 * localStorage is not reliably shared across BrowserWindow instances.
 * Returns true if tokens were found and written to localStorage.
 */
export async function ensureTokensFromElectron(): Promise<boolean> {
	if (typeof window === "undefined" || !window.electronAPI?.getAuthTokens) return false;
	if (getBearerToken()) return true;

	try {
		if (window.electronAPI.getAccessToken) {
			const token = await window.electronAPI.getAccessToken();
			if (token) {
				desktopBearerToken = token;
				return true;
			}
		}
		const tokens = await window.electronAPI.getAuthTokens();
		if (tokens?.bearer) {
			desktopBearerToken = tokens.bearer;
			if (tokens.refresh) {
				desktopRefreshToken = tokens.refresh;
			}
			return true;
		}
	} catch {
		// IPC failure — fall through
	}
	return false;
}

/**
 * Logout the current user by revoking the refresh token and clearing localStorage.
 * Returns true if logout was successful (or tokens were cleared), false otherwise.
 */
export async function logout(): Promise<boolean> {
	const refreshToken = getRefreshToken();
	const isDesktop = isDesktopClient();

	if (isDesktop && window.electronAPI?.logout) {
		await window.electronAPI.logout();
		clearAllTokens();
		return true;
	}

	// Call backend to revoke the refresh token
	if (refreshToken || !isDesktop) {
		try {
			const response = await fetch(buildBackendUrl("/auth/jwt/revoke"), {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				credentials: "include",
				...(refreshToken ? { body: JSON.stringify({ refresh_token: refreshToken }) } : {}),
			});

			if (!response.ok) {
				console.warn("Failed to revoke refresh token:", response.status, await response.text());
			}
		} catch (error) {
			console.warn("Failed to revoke refresh token on server:", error);
			// Continue to clear local tokens even if server call fails
		}
	}

	// Clear all tokens from localStorage
	clearAllTokens();
	return true;
}

/**
 * Checks if the user is authenticated (has a token)
 */
export function isAuthenticated(): boolean {
	return isDesktopClient() ? !!getBearerToken() : true;
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
	const excludedPaths = ["/auth", "/auth/callback", "/", "/login", "/register", "/desktop/login"];
	if (!excludedPaths.includes(window.location.pathname)) {
		setRedirectPath(currentPath);
	}

	window.location.href = getLoginPath();
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
async function doRefreshSession(): Promise<string | null> {
	const currentRefreshToken = getRefreshToken();
	if (isDesktopClient() && !currentRefreshToken) {
		if (window.electronAPI?.refreshAccessToken) {
			const token = await window.electronAPI.refreshAccessToken();
			if (token) {
				desktopBearerToken = token;
			}
			return token;
		}
		return null;
	}

	try {
		const response = await fetch(buildBackendUrl("/auth/jwt/refresh"), {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			credentials: "include",
			...(currentRefreshToken ? { body: JSON.stringify({ refresh_token: currentRefreshToken }) } : {}),
		});

		if (!response.ok) {
			clearAllTokens();
			return null;
		}

		const data = await response.json();
		if (isDesktopClient() && data.access_token) {
			setBearerToken(data.access_token);
			if (data.refresh_token) {
				setRefreshToken(data.refresh_token);
			}
		}
		return data.access_token ?? null;
	} catch {
		return null;
	}
}

export async function refreshSession(): Promise<string | null> {
	if (typeof navigator !== "undefined" && "locks" in navigator) {
		return navigator.locks.request("ss-token-refresh", () => doRefreshSession());
	}
	return doRefreshSession();
}

export async function refreshAccessToken(): Promise<string | null> {
	return refreshSession();
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
		credentials: "include",
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
					credentials: "include",
				});
			}
		}

		// Refresh failed or was skipped, redirect to login
		handleUnauthorized();
		throw new Error("Unauthorized: Redirecting to login page");
	}

	return response;
}
