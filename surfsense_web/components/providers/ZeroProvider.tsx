"use client";

import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { useAtomValue } from "jotai";
import { useEffect, useRef } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { getBearerToken, handleUnauthorized, refreshAccessToken } from "@/lib/auth-utils";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const cacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848";

function ZeroAuthGuard({ children }: { children: React.ReactNode }) {
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

	return <>{children}</>;
}

export function ZeroProvider({ children }: { children: React.ReactNode }) {
	const { data: user } = useAtomValue(currentUserAtom);
	const token = getBearerToken();

	if (!user?.id || !token) {
		return <>{children}</>;
	}

	const userID = String(user.id);
	const context = { userId: userID };
	const auth = token;

	return (
		<ZeroReactProvider {...{ userID, context, cacheURL, schema, queries, auth }}>
			<ZeroAuthGuard>{children}</ZeroAuthGuard>
		</ZeroReactProvider>
	);
}
