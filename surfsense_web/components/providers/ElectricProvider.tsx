"use client";

import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getBearerToken } from "@/lib/auth-utils";
import {
	cleanupElectric,
	type ElectricClient,
	initElectric,
	isElectricInitialized,
} from "@/lib/electric/client";
import { ElectricContext } from "@/lib/electric/context";

interface ElectricProviderProps {
	children: React.ReactNode;
}

/**
 * Initializes user-specific PGlite database with Electric SQL sync.
 * Handles user isolation, cleanup, and re-initialization on user change.
 */
export function ElectricProvider({ children }: ElectricProviderProps) {
	const [electricClient, setElectricClient] = useState<ElectricClient | null>(null);
	const [error, setError] = useState<Error | null>(null);
	const {
		data: user,
		isSuccess: isUserLoaded,
		isError: isUserError,
	} = useAtomValue(currentUserAtom);
	const previousUserIdRef = useRef<string | null>(null);
	const initializingRef = useRef(false);
	const pathname = usePathname();

	useEffect(() => {
		if (typeof window === "undefined") return;

		// No user logged in - cleanup if previous user existed
		if (!isUserLoaded || !user?.id) {
			if (previousUserIdRef.current && isElectricInitialized()) {
				console.log("[ElectricProvider] User logged out, cleaning up...");
				cleanupElectric().then(() => {
					previousUserIdRef.current = null;
					setElectricClient(null);
				});
			}
			return;
		}

		const userId = String(user.id);

		// Skip if already initialized for this user or currently initializing
		if ((electricClient && previousUserIdRef.current === userId) || initializingRef.current) {
			return;
		}

		initializingRef.current = true;
		let mounted = true;

		async function init() {
			try {
				console.log(`[ElectricProvider] Initializing for user: ${userId}`);
				const client = await initElectric(userId);

				if (mounted) {
					previousUserIdRef.current = userId;
					setElectricClient(client);
					setError(null);
					console.log(`[ElectricProvider] ✅ Ready for user: ${userId}`);
				}
			} catch (err) {
				console.error("[ElectricProvider] Failed to initialize:", err);
				if (mounted) {
					setError(err instanceof Error ? err : new Error("Failed to initialize Electric SQL"));
					setElectricClient(null);
				}
			} finally {
				if (mounted) {
					initializingRef.current = false;
				}
			}
		}

		init();
		return () => {
			mounted = false;
		};
	}, [user?.id, isUserLoaded, electricClient]);

	const hasToken = typeof window !== "undefined" && !!getBearerToken();

	// Only block UI on dashboard routes; public pages render immediately
	const requiresElectricLoading = pathname?.startsWith("/dashboard");
	const shouldShowLoading =
		hasToken && isUserLoaded && !!user?.id && !electricClient && !error && requiresElectricLoading;

	useGlobalLoadingEffect(shouldShowLoading);

	// Render immediately for unauthenticated users or failed user queries
	if (!hasToken || !isUserLoaded || !user?.id || isUserError) {
		return <ElectricContext.Provider value={null}>{children}</ElectricContext.Provider>;
	}

	// Render with null context while initializing
	if (!electricClient && !error) {
		return <ElectricContext.Provider value={null}>{children}</ElectricContext.Provider>;
	}

	if (error) {
		console.warn("[ElectricProvider] Initialization failed, sync may not work:", error.message);
	}

	return <ElectricContext.Provider value={electricClient}>{children}</ElectricContext.Provider>;
}
