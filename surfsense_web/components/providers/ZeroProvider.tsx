"use client";

import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { useAtomValue } from "jotai";
import { useEffect, useMemo, useRef } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { getBearerToken, handleUnauthorized, refreshAccessToken } from "@/lib/auth-utils";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const cacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848";

function ZeroAuthSync() {
	const zero = useZero();
	const connectionState = useConnectionState();
	const isRefreshingRef = useRef(false);

	useEffect(() => {
		if (connectionState.name !== "needs-auth" || isRefreshingRef.current) return;

		isRefreshingRef.current = true;

		refreshAccessToken()
			.then((newToken) => {
				if (newToken) {
					zero.connection.connect({ auth: newToken });
				} else {
					handleUnauthorized();
				}
			})
			.finally(() => {
				isRefreshingRef.current = false;
			});
	}, [connectionState, zero]);

	return null;
}

export function ZeroProvider({ children }: { children: React.ReactNode }) {
	const { data: user } = useAtomValue(currentUserAtom);

	const userId = user?.id;
	const hasUser = !!userId;
	const userID = hasUser ? String(userId) : "anon";
	// getBearerToken() returns a string (a primitive), so it's safe to read
	// on every render — reference equality holds as long as the token is
	// unchanged, which keeps the memoized `opts` below stable.
	const auth = hasUser ? getBearerToken() || undefined : undefined;

	const context = useMemo(
		() => (hasUser ? { userId: String(userId) } : undefined),
		[hasUser, userId],
	);

	const opts = useMemo(
		() => ({
			userID,
			schema,
			queries,
			context,
			cacheURL,
			auth,
		}),
		[userID, context, auth],
	);

	return (
		<ZeroReactProvider {...opts}>
			{hasUser && <ZeroAuthSync />}
			{children}
		</ZeroReactProvider>
	);
}
