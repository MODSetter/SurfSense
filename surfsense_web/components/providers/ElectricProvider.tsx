"use client";

import { useAtomValue } from "jotai";
import { useEffect, useRef, useState } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
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
 * ElectricProvider initializes the Electric SQL client with user-specific PGlite database
 * and provides it to children via context.
 *
 * KEY BEHAVIORS:
 * 1. Single initialization point - only this provider creates the Electric client
 * 2. Creates user-specific database (isolated per user)
 * 3. Cleans up other users' databases on login
 * 4. Re-initializes when user changes
 * 5. Provides client via context - hooks should use useElectricClient()
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

	useEffect(() => {
		// Skip on server side
		if (typeof window === "undefined") return;

		// If no user is logged in, don't initialize Electric
		// The app can still function without real-time sync for non-authenticated pages
		if (!isUserLoaded || !user?.id) {
			// If we had a previous user and now logged out, cleanup
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

		// If already initialized for THIS user, skip
		if (electricClient && previousUserIdRef.current === userId) {
			return;
		}

		// Prevent concurrent initialization attempts
		if (initializingRef.current) {
			return;
		}

		// User changed or first initialization
		initializingRef.current = true;
		let mounted = true;

		async function init() {
			try {
				console.log(`[ElectricProvider] Initializing for user: ${userId}`);

				// If different user was previously initialized, cleanup will happen inside initElectric
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
					// Set client to null so hooks know initialization failed
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

	// For non-authenticated pages (like landing page), render immediately with null context
	// Also render immediately if user query failed (e.g., token expired)
	if (!isUserLoaded || !user?.id || isUserError) {
		return <ElectricContext.Provider value={null}>{children}</ElectricContext.Provider>;
	}

	// Show loading state while initializing for authenticated users
	if (!electricClient && !error) {
		return (
			<ElectricContext.Provider value={null}>
				<div className="flex items-center justify-center min-h-screen">
					<div className="text-muted-foreground">Initializing...</div>
				</div>
			</ElectricContext.Provider>
		);
	}

	// If there's an error, still render but warn
	if (error) {
		console.warn("[ElectricProvider] Initialization failed, sync may not work:", error.message);
	}

	// Provide the Electric client to children
	return <ElectricContext.Provider value={electricClient}>{children}</ElectricContext.Provider>;
}
