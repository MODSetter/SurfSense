"use client";

import { useEffect } from "react";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { getAndClearRedirectPath } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginSuccess } from "@/lib/posthog/events";

interface TokenHandlerProps {
	redirectPath?: string; // Default path to redirect after storing token (if no saved path)
	tokenParamName?: string; // Deprecated: tokens are no longer read from URLs
}

/**
 * Client component that finalizes a cookie session after OAuth/local login.
 * After confirming the session, it redirects the user back to the page they were on before
 * being redirected to login (if available), or to the default redirectPath.
 *
 * @param redirectPath - Default path to redirect after storing token (default: '/dashboard')
 * @param tokenParamName - Name of the URL parameter containing the token (default: 'token')
 */
const TokenHandler = ({
	redirectPath = "/dashboard",
	tokenParamName: _tokenParamName = "token",
}: TokenHandlerProps) => {
	// Always show loading for this component - spinner animation won't reset
	useGlobalLoadingEffect(true);

	useEffect(() => {
		if (typeof window === "undefined") return;

		const run = async () => {
			try {
				const sessionResponse = await fetch(buildBackendUrl("/auth/session"), {
					credentials: "include",
				});
				if (!sessionResponse.ok) {
					window.location.href = "/login";
					return;
				}

				const alreadyTracked = sessionStorage.getItem("login_success_tracked");
				if (!alreadyTracked) {
					trackLoginSuccess("google");
				}
				sessionStorage.removeItem("login_success_tracked");

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
				console.error("Error finalizing session:", error);
				window.location.href = redirectPath;
			}
		};

		run();
	}, [redirectPath]);

	// Return null - the global provider handles the loading UI
	return null;
};

export default TokenHandler;
