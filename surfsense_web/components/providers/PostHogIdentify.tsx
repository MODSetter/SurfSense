"use client";

import { useAtomValue } from "jotai";
import { useEffect, useRef } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { identifyUser, resetUser } from "@/lib/posthog/events";

/**
 * Component that handles PostHog user identification.
 * - Identifies users when they're logged in (user data is available)
 * - Resets the PostHog identity when user logs out
 *
 * This should be rendered inside the PostHogProvider.
 */
export function PostHogIdentify() {
	const { data: user, isSuccess, isError } = useAtomValue(currentUserAtom);
	const previousUserIdRef = useRef<string | null>(null);

	useEffect(() => {
		// Only run on client side
		if (typeof window === "undefined") return;

		// User is logged in and we have their data
		if (isSuccess && user?.id) {
			const userId = String(user.id);

			// Only identify if this is a new user or different from previous
			if (previousUserIdRef.current !== userId) {
				identifyUser(userId, {
					email: user.email,
					// Add any other user properties you want to track
					is_superuser: user.is_superuser,
					is_verified: user.is_verified,
				});
				previousUserIdRef.current = userId;
			}
		}

		// User is not logged in (query failed due to auth error)
		// and we previously had a user identified
		if (isError && previousUserIdRef.current !== null) {
			resetUser();
			previousUserIdRef.current = null;
		}
	}, [user, isSuccess, isError]);

	// This component doesn't render anything
	return null;
}
