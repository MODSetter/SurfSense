"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
	clearSSOCookies,
	getBearerToken,
	getSSOCookieTokens,
	setBearerToken,
	setRefreshToken,
} from "@/lib/auth-utils";

/**
 * SSO-only home route.
 *
 * This fork is configured for mPass/Cognito SSO via oauth2-proxy, so the
 * marketing landing page (HeroSection / FeaturesCards / etc.) is never the
 * intended destination — every visitor either has a session or is about to
 * get one. Rendering the marketing JSX here would cause a visible flash
 * (~200-500ms) before the redirect chain completes:
 *
 *   /  →  marketing flash  →  /auth/jwt/proxy-login  →  /  →  /dashboard
 *
 * Instead we render a neutral splash and let the cookie handoff or proxy
 * redirect take the user where they need to go.
 */
export default function HomePage() {
	const router = useRouter();

	useEffect(() => {
		if (getBearerToken()) {
			router.replace("/dashboard");
			return;
		}

		// Cookie handoff from /auth/jwt/proxy-login after oauth2-proxy + Cognito login.
		// Backend sets short-lived cookies (60s TTL) and redirects here instead of
		// to /auth/callback, avoiding any Traefik path-split between frontend and backend.
		const { token, refreshToken } = getSSOCookieTokens();
		if (token) {
			setBearerToken(token);
			if (refreshToken) setRefreshToken(refreshToken);
			clearSSOCookies();
			router.replace("/dashboard");
			return;
		}

		// No JWT anywhere → start the SSO flow.
		window.location.href = `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/jwt/proxy-login`;
	}, [router]);

	// Splash — neutral background, no UI flash during the redirect dance.
	return <div className="min-h-screen bg-gray-50 dark:bg-black" />;
}
