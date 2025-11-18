/**
 * Authentication utility functions for session management
 */

import { baseApiService } from "./apis/base-api.service";

/**
 * Handle session expiration by clearing tokens and redirecting to login
 * This centralizes the 401 handling logic to avoid code duplication
 */
export function handleSessionExpired(): never {
	// Clear token from localStorage
	localStorage.removeItem("surfsense_bearer_token");

	// Clear token from baseApiService singleton to prevent stale auth state
	baseApiService.setBearerToken("");

	// Redirect to login with error parameter for user feedback
	window.location.href = "/login?error=session_expired";

	// Throw to stop further execution (this line won't actually run due to redirect)
	throw new Error("Session expired: Redirecting to login page");
}

/**
 * Check if a response indicates an authentication error
 * @param response - The fetch Response object
 * @returns True if the response status is 401
 */
export function isUnauthorizedResponse(response: Response): boolean {
	return response.status === 401;
}

/**
 * Handle API response with automatic session expiration handling
 * @param response - The fetch Response object
 * @throws Error if response is 401 (after handling session expiration)
 */
export function handleAuthResponse(response: Response): void {
	if (isUnauthorizedResponse(response)) {
		handleSessionExpired();
	}
}
