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

	const hasUser = !!user?.id;
	const userID = hasUser ? String(user.id) : "anon";
	const context = hasUser ? { userId: String(user.id) } : undefined;
	const auth = hasUser ? getBearerToken() || undefined : undefined;

	const opts = useMemo(
		() => ({
			userID,
			schema,
			queries,
			context,
			cacheURL,
			auth,
		}),
		[userID, schema, queries, context, cacheURL, auth],
	);

	return (
		<ZeroReactProvider {...opts}>
			{hasUser && <ZeroAuthSync />}
			{children}
		</ZeroReactProvider>
	);
}
