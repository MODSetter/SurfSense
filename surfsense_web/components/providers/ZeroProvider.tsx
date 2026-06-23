"use client";

import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { useEffect, useMemo } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { useSession } from "@/hooks/use-session";
import {
	getBearerToken,
	handleUnauthorized,
	isPublicRoute,
	refreshAccessToken,
} from "@/lib/auth-utils";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const configuredCacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL;

function getCacheURL() {
	if (configuredCacheURL) return configuredCacheURL;
	if (typeof window !== "undefined") {
		return `${window.location.origin}/zero`;
	}
	return "http://localhost:4848";
}

function ZeroAuthSync({ isDesktop }: { isDesktop: boolean }) {
	const zero = useZero();
	const connectionState = useConnectionState();

	useEffect(() => {
		if (connectionState.name !== "needs-auth") return;

		refreshAccessToken().then((newToken) => {
			if (!newToken) {
				handleUnauthorized();
				return;
			}

			if (isDesktop) {
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
	const { data: user, isLoading } = useAtomValue(currentUserAtom);

	const userId = user?.id;
	const userID = userId ? String(userId) : undefined;

	if (isLoading || !userID) {
		return <>{children}</>;
	}

	return (
		<ZeroClientProvider userID={userID} isDesktop={isDesktop}>
			{children}
		</ZeroClientProvider>
	);
}

function ZeroClientProvider({
	children,
	userID,
	isDesktop,
}: {
	children: React.ReactNode;
	userID: string;
	isDesktop: boolean;
}) {
	const cacheURL = useMemo(() => getCacheURL(), []);
	const auth = isDesktop ? getBearerToken() || undefined : undefined;
	const context = useMemo(() => ({ userId: userID }), [userID]);

	const opts = useMemo(
		() => ({
			userID,
			schema,
			queries,
			context,
			cacheURL,
			auth,
		}),
		[userID, context, cacheURL, auth]
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
