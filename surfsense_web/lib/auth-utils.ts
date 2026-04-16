/**
 * Authentication utilities for handling token expiration and redirects
 */

const REDIRECT_PATH_KEY = "surfsense_redirect_path";
const BEARER_TOKEN_KEY = "surfsense_bearer_token";
const REFRESH_TOKEN_KEY = "surfsense_refresh_token";

// Flag to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

/** Path prefixes for routes that do not require auth (no current-user fetch, no redirect on 401) */
const PUBLIC_ROUTE_PREFIXES = [
	"/login",
	"/register",
	"/auth",
	"/desktop/login",
	"/docs",
	"/public",
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
 * Clears tokens and redirects through oauth2-proxy on 401.
 *
 * This fork is SSO-only (mPass/Cognito via oauth2-proxy ForwardAuth), so the
 * only valid recovery from a 401 is bouncing the user through the OIDC flow
 * at the dedicated auth subdomain. The previous /login redirect was a dead
 * page in SSO mode and resulted in a blank screen.
 *
 * Moving this responsibility to the frontend lets the devstack repo drop
 * its SurfSense-specific Traefik `mpass-signin@file` middleware and
 * `auth-redirect.yml` dynamic config — those exist purely to convert API
 * 401s into redirects at the network layer. With this in place the app
 * handles its own 401s before Traefik ever needs to.
 */
export function handleUnauthorized(): void {
	if (typeof window === "undefined") return;

	const pathname = window.location.pathname;

	// Always clear tokens
	localStorage.removeItem(BEARER_TOKEN_KEY);
	localStorage.removeItem(REFRESH_TOKEN_KEY);

	// Public routes (e.g. /docs) don't need auth — don't redirect, just clear.
	if (isPublicRoute(pathname)) return;

	const currentPath = pathname + window.location.search + window.location.hash;
	const excludedPaths = ["/auth", "/"];
	if (!excludedPaths.includes(pathname)) {
		localStorage.setItem(REDIRECT_PATH_KEY, currentPath);
	}

	// Redirect through oauth2-proxy /oauth2/sign_in. The dedicated auth subdomain
	// handles the OIDC dance with Cognito and returns the user to `rd=` on success.
	const oauthProxyUrl = process.env.NEXT_PUBLIC_OAUTH2_PROXY_URL || window.location.origin;
	const rd = window.location.href;
	window.location.href = `${oauthProxyUrl}/oauth2/sign_in?rd=${encodeURIComponent(rd)}`;
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
	syncTokensToElectron();
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
	syncTokensToElectron();
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
 * Pushes the current localStorage tokens into the Electron main process
 * so that other BrowserWindows (Quick Ask, Autocomplete) can access them.
 */
function syncTokensToElectron(): void {
	if (typeof window === "undefined" || !window.electronAPI?.setAuthTokens) return;
	const bearer = localStorage.getItem(BEARER_TOKEN_KEY) || "";
	const refresh = localStorage.getItem(REFRESH_TOKEN_KEY) || "";
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
		const tokens = await window.electronAPI.getAuthTokens();
		if (tokens?.bearer) {
			localStorage.setItem(BEARER_TOKEN_KEY, tokens.bearer);
			if (tokens.refresh) {
				localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
			}
			return true;
		}
	} catch {
		// IPC failure — fall through
	}
	return false;
}

/**
 * Reads the short-lived SSO handoff cookies set by /auth/jwt/proxy-login.
 * Returns null for each if not present.
 */
export function getSSOCookieTokens(): { token: string | null; refreshToken: string | null } {
	if (typeof document === "undefined") return { token: null, refreshToken: null };
	const get = (name: string): string | null => {
		const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
		return match ? decodeURIComponent(match[1]) : null;
	};
	return { token: get("surfsense_sso_token"), refreshToken: get("surfsense_sso_refresh_token") };
}

/**
 * Clears the SSO handoff cookies after tokens have been transferred to localStorage.
 */
export function clearSSOCookies(): void {
	if (typeof document === "undefined") return;
	const expire = "expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
	document.cookie = `surfsense_sso_token=; ${expire}`;
	document.cookie = `surfsense_sso_refresh_token=; ${expire}`;
}

/**
 * Logout the current user.
 *
 *   Layer 1 — revoke JWT refresh tokens server-side
 *   Layer 2 — clear _oauth2_proxy cookie via /oauth2/sign_out
 *   Layer 3 (optional) — clear Cognito session via rd= redirect when OIDC_LOGOUT_URL configured
 */
export async function logout(): Promise<boolean> {
	const refreshToken = getRefreshToken();

	// Layer 1 — revoke the refresh token server-side
	if (refreshToken) {
		try {
			const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
			const response = await fetch(`${backendUrl}/auth/jwt/revoke`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ refresh_token: refreshToken }),
			});
			if (!response.ok) {
				console.warn("Failed to revoke refresh token:", response.status, await response.text());
			}
		} catch (error) {
			console.warn("Failed to revoke refresh token on server:", error);
		}
	}

	clearAllTokens();

	// Layer 2 (+ optional Layer 3) — oauth2-proxy sign_out, with Cognito hop if configured.
	if (typeof window !== "undefined") {
		const oauthProxyUrl = process.env.NEXT_PUBLIC_OAUTH2_PROXY_URL || window.location.origin;
		const logoutRedirect = process.env.NEXT_PUBLIC_LOGOUT_REDIRECT_URL || window.location.origin;
		const oidcLogoutUrl = process.env.NEXT_PUBLIC_OIDC_LOGOUT_URL;
		const oidcClientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;

		let rdParam: string;
		if (oidcLogoutUrl && oidcClientId) {
			// Full 3-layer logout: oauth2-proxy → Cognito → landing page.
			// Single-encode query params so oauth2-proxy decodes once and passes clean args
			// to Cognito; encodeURIComponent would double-encode and Cognito would reject.
			const cognitoUrl = new URL(oidcLogoutUrl);
			cognitoUrl.searchParams.set("client_id", oidcClientId);
			cognitoUrl.searchParams.set("logout_uri", logoutRedirect);
			rdParam = cognitoUrl
				.toString()
				.replace(/\?/, "%3F")
				.replace(/&/g, "%26")
				.replace(/=/g, "%3D");
		} else {
			// No Cognito hosted logout — clear oauth2-proxy cookie and land on portal.
			rdParam = encodeURIComponent(logoutRedirect);
		}
		window.location.href = `${oauthProxyUrl}/oauth2/sign_out?rd=${rdParam}`;
		return true; // browser is already navigating away
	}

	return false; // SSR — caller should navigate
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
	const excludedPaths = ["/auth", "/", "/login", "/register"];
	if (!excludedPaths.includes(window.location.pathname)) {
		localStorage.setItem(REDIRECT_PATH_KEY, currentPath);
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
export async function refreshAccessToken(): Promise<string | null> {
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
			const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
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
