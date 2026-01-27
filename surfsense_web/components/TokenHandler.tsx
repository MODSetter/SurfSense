"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getAndClearRedirectPath, setBearerToken } from "@/lib/auth-utils";
import { trackLoginSuccess } from "@/lib/posthog/events";

interface TokenHandlerProps {
	redirectPath?: string; // Default path to redirect after storing token (if no saved path)
	tokenParamName?: string; // Name of the URL parameter containing the token
	storageKey?: string; // Key to use when storing in localStorage (kept for backwards compatibility)
}

/**
 * Client component that extracts a token from URL parameters and stores it in localStorage
 * After storing the token, it redirects the user back to the page they were on before
 * being redirected to login (if available), or to the default redirectPath.
 *
 * @param redirectPath - Default path to redirect after storing token (default: '/dashboard')
 * @param tokenParamName - Name of the URL parameter containing the token (default: 'token')
 * @param storageKey - Key to use when storing in localStorage (default: 'surfsense_bearer_token')
 */
const TokenHandler = ({
	redirectPath = "/dashboard",
	tokenParamName = "token",
	storageKey = "surfsense_bearer_token",
}: TokenHandlerProps) => {
	const searchParams = useSearchParams();

	// Always show loading for this component - spinner animation won't reset
	useGlobalLoadingEffect(true);

	useEffect(() => {
		// Only run on client-side
		if (typeof window === "undefined") return;

		// Get token from URL parameters
		const token = searchParams.get(tokenParamName);

		if (token) {
			try {
				// Track login success for OAuth flows (e.g., Google)
				// Local login already tracks success before redirecting here
				const alreadyTracked = sessionStorage.getItem("login_success_tracked");
				if (!alreadyTracked) {
					// This is an OAuth flow (Google login) - track success
					trackLoginSuccess("google");
				}
				// Clear the flag for future logins
				sessionStorage.removeItem("login_success_tracked");

				// Store token in localStorage using both methods for compatibility
				localStorage.setItem(storageKey, token);
				setBearerToken(token);

				// Check if there's a saved redirect path from before the auth flow
				const savedRedirectPath = getAndClearRedirectPath();

				// Use the saved path if available, otherwise use the default redirectPath
				const finalRedirectPath = savedRedirectPath || redirectPath;

				// Redirect to the appropriate path
				window.location.href = finalRedirectPath;
			} catch (error) {
				console.error("Error storing token in localStorage:", error);
				// Even if there's an error, try to redirect to the default path
				window.location.href = redirectPath;
			}
		}
	}, [searchParams, tokenParamName, storageKey, redirectPath]);

	// Return null - the global provider handles the loading UI
	return null;
};

export default TokenHandler;
