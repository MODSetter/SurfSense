"use client";

import { useEffect } from "react";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { getAndClearRedirectPath, setBearerToken, setRefreshToken } from "@/lib/auth-utils";
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
	// Always show loading for this component - spinner animation won't reset
	useGlobalLoadingEffect(true);

	useEffect(() => {
		if (typeof window === "undefined") return;

		const run = async () => {
			const params = new URLSearchParams(window.location.search);
			const token = params.get(tokenParamName);
			const refreshToken = params.get("refresh_token");

			if (token) {
				try {
					const alreadyTracked = sessionStorage.getItem("login_success_tracked");
					if (!alreadyTracked) {
						trackLoginSuccess("google");
					}
					sessionStorage.removeItem("login_success_tracked");

					localStorage.setItem(storageKey, token);
					setBearerToken(token);

					if (refreshToken) {
						setRefreshToken(refreshToken);
					}

					// Auto-set active search space in desktop if not already set
					if (window.electronAPI?.getActiveSearchSpace) {
						try {
							const stored = await window.electronAPI.getActiveSearchSpace();
							if (!stored) {
								const spaces = await searchSpacesApiService.getSearchSpaces();
								if (spaces?.length) {
									await window.electronAPI.setActiveSearchSpace?.(String(spaces[0].id));
								}
							}
						} catch {
							// non-critical
						}
					}

					const savedRedirectPath = getAndClearRedirectPath();
					const finalRedirectPath = savedRedirectPath || redirectPath;
					window.location.href = finalRedirectPath;
				} catch (error) {
					console.error("Error storing token in localStorage:", error);
					window.location.href = redirectPath;
				}
			}
		};

		run();
	}, [tokenParamName, storageKey, redirectPath]);

	// Return null - the global provider handles the loading UI
	return null;
};

export default TokenHandler;
