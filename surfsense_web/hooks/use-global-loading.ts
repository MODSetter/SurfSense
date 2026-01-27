"use client";

import { useAtom } from "jotai";
import { useCallback, useEffect, useRef } from "react";
import { globalLoadingAtom } from "@/atoms/ui/loading.atoms";

// Global counter to generate unique IDs for each loading request
let loadingIdCounter = 0;

// Track the current active loading ID globally
let currentLoadingId: number | null = null;

// Pending hide timeout - allows new loading requests to take over before hiding
let pendingHideTimeout: ReturnType<typeof setTimeout> | null = null;

/**
 * Hook to control the global loading screen.
 * The spinner is always mounted in the DOM to prevent animation reset.
 */
export function useGlobalLoading() {
	const [loading, setLoading] = useAtom(globalLoadingAtom);

	const show = useCallback(() => {
		// Cancel any pending hide - new loading request takes over
		if (pendingHideTimeout) {
			clearTimeout(pendingHideTimeout);
			pendingHideTimeout = null;
		}

		const id = ++loadingIdCounter;
		currentLoadingId = id;
		setLoading({ isLoading: true });
		return id;
	}, [setLoading]);

	const hide = useCallback(
		(id?: number) => {
			// Only hide if this is the current loading, or if no ID provided (force hide)
			if (id === undefined || id === currentLoadingId) {
				// Use a small delay to allow React to flush pending mounts
				// This prevents flash when transitioning between loading states
				if (pendingHideTimeout) {
					clearTimeout(pendingHideTimeout);
				}

				pendingHideTimeout = setTimeout(() => {
					// Double-check we're still the current loading after the delay
					if (id === undefined || id === currentLoadingId) {
						currentLoadingId = null;
						setLoading({ isLoading: false });
					}
					pendingHideTimeout = null;
				}, 50); // Small delay to allow next component to mount and show loading
			}
		},
		[setLoading]
	);

	return { show, hide, isLoading: loading.isLoading };
}

/**
 * Hook that automatically shows/hides the global loading screen based on a condition.
 * Useful for components that show loading on mount and hide on unmount.
 *
 * Uses ownership tracking to prevent flashes when multiple components
 * transition loading states (e.g., layout → page).
 *
 * @param shouldShow - Whether the loading screen should be visible
 */
export function useGlobalLoadingEffect(shouldShow: boolean) {
	const { show, hide } = useGlobalLoading();
	const loadingIdRef = useRef<number | null>(null);

	useEffect(() => {
		if (shouldShow) {
			// Show loading and store the ID
			loadingIdRef.current = show();
		} else if (loadingIdRef.current !== null) {
			// Only hide if we were the ones showing loading
			hide(loadingIdRef.current);
			loadingIdRef.current = null;
		}
	}, [shouldShow, show, hide]);

	// Cleanup on unmount - only hide if we're still the active loading
	useEffect(() => {
		return () => {
			if (loadingIdRef.current !== null) {
				hide(loadingIdRef.current);
				loadingIdRef.current = null;
			}
		};
	}, [hide]);
}
