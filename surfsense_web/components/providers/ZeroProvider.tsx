"use client";

import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "@/hooks/use-session";
import { authenticatedFetch, getDesktopAccessToken } from "@/lib/auth-fetch";
import { handleUnauthorized, isPublicRoute, refreshSession } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";
import type { Context } from "@/types/zero";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const configuredCacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL;
type ZeroContext = Exclude<Context, undefined>;
type LoadedZeroContext = {
	context: ZeroContext;
	desktopAuth?: string;
};

function getCacheURL() {
	if (configuredCacheURL) return configuredCacheURL;
	if (typeof window !== "undefined") {
		return `${window.location.origin}/zero`;
	}
	return "http://localhost:4848";
}

async function fetchZeroContext(isDesktop: boolean): Promise<LoadedZeroContext | null> {
	const response = await authenticatedFetch(buildBackendUrl("/zero/context"), {
		skipAuthRedirect: true,
	});
	if (!response.ok) return null;

	return {
		context: (await response.json()) as ZeroContext,
		desktopAuth: isDesktop ? (await getDesktopAccessToken()) || undefined : undefined,
	};
}

// Cap how many times we will refresh the session in response to Zero's
// `needs-auth` state before giving up. Without this, a persistent auth failure
// in zero-cache makes the connection cycle needs-auth -> connecting -> needs-auth
// indefinitely, each cycle firing a `/auth/jwt/refresh` and quickly tripping the
// backend rate limiter (HTTP 429).
const MAX_ZERO_AUTH_REFRESH_ATTEMPTS = 3;
const ZERO_AUTH_REFRESH_BASE_DELAY_MS = 1_000;
const ZERO_AUTH_REFRESH_MAX_DELAY_MS = 30_000;

function ZeroAuthSync({ isDesktop }: { isDesktop: boolean }) {
	const zero = useZero();
	const connectionState = useConnectionState();
	const refreshAttemptsRef = useRef(0);
	const refreshInFlightRef = useRef(false);

	// Once a connection is established, clear the backoff so future
	// auth expirations get a fresh set of refresh attempts.
	useEffect(() => {
		if (connectionState.name === "connected") {
			refreshAttemptsRef.current = 0;
		}
	}, [connectionState.name]);

	useEffect(() => {
		if (connectionState.name !== "needs-auth") return;
		if (refreshInFlightRef.current) return;

		if (refreshAttemptsRef.current >= MAX_ZERO_AUTH_REFRESH_ATTEMPTS) {
			handleUnauthorized();
			return;
		}

		const attempt = refreshAttemptsRef.current;
		const delayMs =
			attempt === 0
				? 0
				: Math.min(
						ZERO_AUTH_REFRESH_BASE_DELAY_MS * 2 ** (attempt - 1),
						ZERO_AUTH_REFRESH_MAX_DELAY_MS
					);

		refreshInFlightRef.current = true;
		const timer = setTimeout(() => {
			refreshAttemptsRef.current += 1;
			refreshSession()
				.then(async (refreshed) => {
					if (!refreshed) {
						handleUnauthorized();
						return;
					}

					if (isDesktop) {
						const newToken = await getDesktopAccessToken({ forceRefresh: true });
						if (!newToken) {
							handleUnauthorized();
							return;
						}
						zero.connection.connect({ auth: newToken });
					} else {
						zero.connection.connect();
					}
				})
				.finally(() => {
					refreshInFlightRef.current = false;
				});
		}, delayMs);

		return () => clearTimeout(timer);
	}, [connectionState.name, isDesktop, zero]);

	useEffect(() => {
		if (typeof window === "undefined" || !window.electronAPI?.onAuthChanged) return;
		return window.electronAPI.onAuthChanged(({ accessToken }) => {
			if (accessToken) {
				zero.connection.connect({ auth: accessToken });
			}
		});
	}, [zero]);

	return null;
}

function AuthenticatedZeroProvider({
	children,
	isDesktop,
}: {
	children: React.ReactNode;
	isDesktop: boolean;
}) {
	const [loadedContext, setLoadedContext] = useState<LoadedZeroContext | null>(null);

	useEffect(() => {
		let isMounted = true;

		const load = async () => {
			const nextContext = await fetchZeroContext(isDesktop);
			if (isMounted) {
				setLoadedContext(nextContext);
			}
		};

		void load();

		if (!isDesktop || typeof window === "undefined" || !window.electronAPI?.onAuthChanged) {
			return () => {
				isMounted = false;
			};
		}

		const unsubscribe = window.electronAPI.onAuthChanged(({ accessToken }) => {
			if (!accessToken) {
				setLoadedContext(null);
				return;
			}
			void load();
		});

		return () => {
			isMounted = false;
			unsubscribe();
		};
	}, [isDesktop]);

	if (!loadedContext) {
		return <>{children}</>;
	}

	return (
		<ZeroClientProvider
			userID={loadedContext.context.userId}
			context={loadedContext.context}
			isDesktop={isDesktop}
			initialDesktopAuth={loadedContext.desktopAuth}
		>
			{children}
		</ZeroClientProvider>
	);
}

function ZeroClientProvider({
	children,
	userID,
	context,
	isDesktop,
	initialDesktopAuth,
}: {
	children: React.ReactNode;
	userID: string;
	context: ZeroContext;
	isDesktop: boolean;
	initialDesktopAuth?: string;
}) {
	const cacheURL = useMemo(() => getCacheURL(), []);
	const [desktopAuth, setDesktopAuth] = useState<string | undefined>(initialDesktopAuth);

	useEffect(() => {
		setDesktopAuth(initialDesktopAuth);
	}, [initialDesktopAuth]);

	useEffect(() => {
		if (!isDesktop) return;
		let isMounted = true;
		getDesktopAccessToken().then((token) => {
			if (isMounted) setDesktopAuth(token || undefined);
		});
		return () => {
			isMounted = false;
		};
	}, [isDesktop]);

	const opts = useMemo(
		() => ({
			userID,
			schema,
			queries,
			context,
			cacheURL,
			auth: isDesktop ? desktopAuth : undefined,
		}),
		[userID, context, cacheURL, isDesktop, desktopAuth]
	);

	return (
		<ZeroReactProvider {...opts}>
			<ZeroAuthSync isDesktop={isDesktop} />
			{children}
		</ZeroReactProvider>
	);
}

function WebZeroProvider({ children }: { children: React.ReactNode }) {
	const session = useSession();

	if (session.status !== "authenticated") {
		return <>{children}</>;
	}

	return <AuthenticatedZeroProvider isDesktop={false}>{children}</AuthenticatedZeroProvider>;
}

function DesktopZeroProvider({ children }: { children: React.ReactNode }) {
	return <AuthenticatedZeroProvider isDesktop>{children}</AuthenticatedZeroProvider>;
}

export function ZeroProvider({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();
	const isDesktop = typeof window !== "undefined" && !!window.electronAPI;

	if (!isDesktop && isPublicRoute(pathname)) {
		return <>{children}</>;
	}

	if (isDesktop) {
		return <DesktopZeroProvider>{children}</DesktopZeroProvider>;
	}

	return <WebZeroProvider>{children}</WebZeroProvider>;
}
