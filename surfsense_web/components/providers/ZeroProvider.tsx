"use client";

import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useSession } from "@/hooks/use-session";
import { getDesktopAccessToken } from "@/lib/auth-fetch";
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
	const headers: HeadersInit = {};
	let desktopAuth: string | undefined;

	if (isDesktop) {
		const token = await getDesktopAccessToken();
		if (!token) return null;
		desktopAuth = token;
		headers.Authorization = `Bearer ${token}`;
	}

	const response = await fetch(buildBackendUrl("/zero/context"), {
		credentials: "include",
		headers,
	});

	if (!response.ok) return null;

	return {
		context: (await response.json()) as ZeroContext,
		desktopAuth,
	};
}

function ZeroAuthSync({ isDesktop }: { isDesktop: boolean }) {
	const zero = useZero();
	const connectionState = useConnectionState();

	useEffect(() => {
		if (connectionState.name !== "needs-auth") return;

		refreshSession().then(async (refreshed) => {
			if (!refreshed) {
				handleUnauthorized();
				return;
			}

			if (isDesktop) {
				const newToken = await getDesktopAccessToken();
				if (!newToken) {
					handleUnauthorized();
					return;
				}
				zero.connection.connect({ auth: newToken });
			} else {
				zero.connection.connect();
			}
		});
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
