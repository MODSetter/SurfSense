/**
 * Authentication utilities for handling session expiration and redirects.
 */
import { buildBackendUrl } from "@/lib/env-config";

const REDIRECT_PATH_KEY = "surfsense_redirect_path";
const LEGACY_BEARER_TOKEN_KEY = "surfsense_bearer_token";
const LEGACY_REFRESH_TOKEN_KEY = "surfsense_refresh_token";

export function isDesktopClient(): boolean {
	return typeof window !== "undefined" && !!window.electronAPI;
}

function purgeLegacyStoredTokens(): void {
	if (typeof window === "undefined") return;
	localStorage.removeItem(LEGACY_BEARER_TOKEN_KEY);
	localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
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
 * Clears auth state and optionally redirects to login.
 * Call this when a 401 response is received.
 * Only redirects when the current route is protected; on public routes we just clear state.
 */
export function handleUnauthorized(): void {
	if (typeof window === "undefined") return;

	const pathname = window.location.pathname;
	purgeLegacyStoredTokens();

	// Only redirect on protected routes; stay on public pages (e.g. /docs)
	if (!isPublicRoute(pathname)) {
		const currentPath = pathname + window.location.search + window.location.hash;
		const excludedPaths = ["/auth", "/"];
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

export function getPostLoginRedirectPath(defaultPath = "/dashboard"): string {
	return getAndClearRedirectPath() || defaultPath;
}

/**
 * Logout the current user by revoking the refresh token and clearing localStorage.
 * Returns true if logout was successful (or tokens were cleared), false otherwise.
 */
export async function logout(): Promise<boolean> {
	const isDesktop = isDesktopClient();

	if (isDesktop && window.electronAPI?.logout) {
		await window.electronAPI.logout();
		purgeLegacyStoredTokens();
		return true;
	}

	try {
		const response = await fetch(buildBackendUrl("/auth/jwt/revoke"), {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			credentials: "include",
		});

		if (!response.ok) {
			console.warn("Failed to revoke refresh token:", response.status, await response.text());
		}
	} catch (error) {
		console.warn("Failed to revoke refresh token on server:", error);
		// Continue to clear local state even if server revoke fails.
	}

	purgeLegacyStoredTokens();
	return true;
}

/**
 * Compatibility helper for legacy query gates.
 *
 * Web auth is cookie-backed, so the client cannot synchronously prove whether a
 * session exists. Return true and let `/auth/session` or API 401s settle it.
 * Desktop can synchronously check for the Electron bridge, while the access
 * token itself is resolved asynchronously by auth-fetch.
 */
export function isAuthenticated(): boolean {
	return true;
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
	const excludedPaths = ["/auth", "/", "/login", "/register", "/desktop/login"];
	if (!excludedPaths.includes(window.location.pathname)) {
		setRedirectPath(currentPath);
	}

	window.location.href = getLoginPath();
}

async function doRefreshSession(): Promise<boolean> {
	if (isDesktopClient()) {
		const token = await window.electronAPI?.refreshAccessToken?.();
		return !!token;
	}

	try {
		const response = await fetch(buildBackendUrl("/auth/jwt/refresh"), {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			credentials: "include",
		});

		if (!response.ok) {
			purgeLegacyStoredTokens();
			return false;
		}

		return true;
	} catch {
		return false;
	}
}

export async function refreshSession(): Promise<boolean> {
	if (typeof navigator !== "undefined" && "locks" in navigator) {
		return navigator.locks.request("ss-token-refresh", () => doRefreshSession());
	}
	return doRefreshSession();
}
