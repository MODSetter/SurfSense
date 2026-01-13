"use client";

import { useEffect, useState } from "react";
import { initElectric, isElectricInitialized } from "@/lib/electric/client";

interface ElectricProviderProps {
	children: React.ReactNode;
}

/**
 * ElectricProvider initializes the Electric SQL client with PGlite
 *
 * This provider ensures Electric is initialized before rendering children,
 * but doesn't block if initialization fails (app can still work without real-time sync)
 */
export function ElectricProvider({ children }: ElectricProviderProps) {
	const [initialized, setInitialized] = useState(false);
	const [error, setError] = useState<Error | null>(null);

	useEffect(() => {
		// Skip if already initialized
		if (isElectricInitialized()) {
			setInitialized(true);
			return;
		}

		let mounted = true;

		async function init() {
			try {
				await initElectric();
				if (mounted) {
					setInitialized(true);
					setError(null);
				}
			} catch (err) {
				console.error("Failed to initialize Electric SQL:", err);
				if (mounted) {
					setError(err instanceof Error ? err : new Error("Failed to initialize Electric SQL"));
					// Don't block rendering if Electric SQL fails - app can still work
					setInitialized(true);
				}
			}
		}

		init();

		return () => {
			mounted = false;
		};
	}, []);

	// Show loading state only briefly, then render children
	// Electric SQL will sync in the background
	if (!initialized) {
		return (
			<div className="flex items-center justify-center min-h-screen">
				<div className="text-muted-foreground">Initializing...</div>
			</div>
		);
	}

	// If there's an error, still render children but log the error
	if (error) {
		console.warn("Electric SQL initialization failed, notifications may not sync:", error.message);
	}

	return <>{children}</>;
}
