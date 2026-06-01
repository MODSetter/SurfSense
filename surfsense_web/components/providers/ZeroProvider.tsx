"use client";

import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { useAtomValue } from "jotai";
import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { getBearerToken, handleUnauthorized, refreshAccessToken } from "@/lib/auth-utils";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const cacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848";

function ZeroAuthSync() {
	const zero = useZero();
	const connectionState = useConnectionState();
	const isRefreshingRef = useRef(false);
	const schemaErrorShownRef = useRef(false);

	useEffect(() => {
		// Handle SchemaVersionNotSupported: the Zero Cache replica is out of sync
		// with the Postgres publication (e.g. `user` table not in zero_publication).
		// This used to cause an infinite reload loop (~60s cycle) because the default
		// `onUpdateNeeded` handler calls `location.reload()`.
		if (connectionState.name === "error" && !schemaErrorShownRef.current) {
			const err = (connectionState as { error?: { message?: string; kind?: string } }).error;
			const isSchemaError = err && (
				err.kind === "SchemaVersionNotSupported" ||
				err.message?.includes("SchemaVersionNotSupported") ||
				err.message?.includes("not one of the replicated tables")
			);

			if (isSchemaError) {
				schemaErrorShownRef.current = true;
				console.error(
					"[ZeroProvider] SchemaVersionNotSupported: The Zero Cache replica is out of sync " +
					"with the Postgres publication. This usually means a newly added table " +
					"(e.g. `user`) was added to `zero_publication` but Zero Cache wasn't notified " +
					"to resync.\n" +
					"Fix: run `docker compose stop zero-cache && docker compose up -d zero-cache` " +
					"to force a fresh initial sync."
				);
				toast.error(
					"Database schema out of sync. Please run: docker compose restart zero-cache"
				);
				// Do NOT trigger a reconnect loop — the schema is fundamentally broken
				// until the user resyncs Zero Cache.
				return;
			}
		}

		// Reset the flag once we're connected (so we re-show the error if it happens again)
		if (connectionState.name === "connected") {
			schemaErrorShownRef.current = false;
		}

		// Existing auth refresh logic
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
		[hasUser, userId]
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
		[userID, context, auth]
	);

	return (
		<ZeroReactProvider {...opts}>
			{hasUser && <ZeroAuthSync />}
			{children}
		</ZeroReactProvider>
	);
}
