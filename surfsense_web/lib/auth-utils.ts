/**
 * Authentication utilities for handling token expiration and redirects
 */

const REDIRECT_PATH_KEY = "surfsense_redirect_path";
const BEARER_TOKEN_KEY = "surfsense_bearer_token";

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

	// Clear the token
	localStorage.removeItem(BEARER_TOKEN_KEY);

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
 * Authenticated fetch wrapper that handles 401 responses uniformly
 * Automatically redirects to login on 401 and saves the current path
 */
export async function authenticatedFetch(
	url: string,
	options?: RequestInit & { skipAuthRedirect?: boolean }
): Promise<Response> {
	const { skipAuthRedirect = false, ...fetchOptions } = options || {};

	const headers = getAuthHeaders(fetchOptions.headers as Record<string, string>);

	const response = await fetch(url, {
		...fetchOptions,
		headers,
	});

	// Handle 401 Unauthorized
	if (response.status === 401 && !skipAuthRedirect) {
		handleUnauthorized();
		throw new Error("Unauthorized: Redirecting to login page");
	}

	return response;
}
