"use client";

import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";

export default function AuthCallbackLoading() {
	// Use global loading - spinner animation won't reset when page transitions
	useGlobalLoadingEffect(true);

	// Return null - the GlobalLoadingProvider handles the loading UI
	return null;
}
