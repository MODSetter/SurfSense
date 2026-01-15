"use client";

import { createContext, useContext } from "react";
import type { ElectricClient } from "./client";

/**
 * Context for sharing the Electric SQL client across the app
 *
 * This ensures:
 * 1. Single initialization point (ElectricProvider only)
 * 2. No race conditions (hooks wait for context)
 * 3. Clean cleanup (ElectricProvider manages lifecycle)
 */
export const ElectricContext = createContext<ElectricClient | null>(null);

/**
 * Hook to get the Electric client from context
 * Returns null if Electric is not initialized yet
 */
export function useElectricClient(): ElectricClient | null {
	return useContext(ElectricContext);
}

/**
 * Hook to get the Electric client, throwing if not available
 * Use this when you're sure Electric should be initialized
 */
export function useElectricClientOrThrow(): ElectricClient {
	const client = useContext(ElectricContext);
	if (!client) {
		throw new Error(
			"Electric client not available. Make sure you're inside ElectricProvider and user is authenticated."
		);
	}
	return client;
}
