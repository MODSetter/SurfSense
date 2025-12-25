"use client";

import { useAtomValue } from "jotai";
import posthog from "posthog-js";
import { PostHogProvider as PHProvider, usePostHog } from "posthog-js/react";
import { useEffect, useRef } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";

// Initialize PostHog only on client side
if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_POSTHOG_KEY) {
	posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
		api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
		person_profiles: "identified_only",
		capture_pageview: true,
		capture_pageleave: true,
		autocapture: false, // We'll use manual event tracking for better control
		persistence: "localStorage",
		loaded: (posthog) => {
			if (process.env.NODE_ENV === "development") {
				// Uncomment to debug in development
				// posthog.debug();
			}
		},
	});
}

/**
 * Component that handles user identification with PostHog
 * Placed inside the provider hierarchy to access user data
 */
function PostHogUserIdentifier() {
	const ph = usePostHog();
	const { data: user, isSuccess } = useAtomValue(currentUserAtom);
	const hasIdentified = useRef(false);

	useEffect(() => {
		if (isSuccess && user && !hasIdentified.current) {
			// Identify the user with PostHog
			ph.identify(user.id, {
				email: user.email,
				is_active: user.is_active,
				is_superuser: user.is_superuser,
				is_verified: user.is_verified,
			});
			hasIdentified.current = true;
		}
	}, [ph, user, isSuccess]);

	// Reset identification flag when user logs out (user becomes null)
	useEffect(() => {
		if (!user && hasIdentified.current) {
			ph.reset();
			hasIdentified.current = false;
		}
	}, [ph, user]);

	return null;
}

/**
 * PostHog Analytics Provider
 * Wraps the app to enable analytics tracking and user identification
 */
export function PostHogProvider({ children }: { children: React.ReactNode }) {
	// Don't render provider if PostHog key is not configured
	if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
		return <>{children}</>;
	}

	return (
		<PHProvider client={posthog}>
			<PostHogUserIdentifier />
			{children}
		</PHProvider>
	);
}
