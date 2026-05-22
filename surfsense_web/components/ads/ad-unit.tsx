"use client";

import type { CSSProperties } from "react";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_ADSENSE_CLIENT_ID;

declare global {
	interface Window {
		adsbygoogle?: Record<string, unknown>[];
	}
}

interface AdUnitProps {
	/** AdSense ad slot ID from your AdSense dashboard. */
	slot: string;
	/** AdSense ad format. Defaults to "auto" for responsive display ads. */
	format?: "auto" | "fluid" | "rectangle" | "vertical" | "horizontal";
	/** Optional layout (e.g. "in-article"). */
	layout?: string;
	/** Optional layout key (required for in-feed ads). */
	layoutKey?: string;
	/** Full-width responsive on mobile. Defaults to true. */
	responsive?: boolean;
	className?: string;
	style?: CSSProperties;
}

/**
 * Renders a Google AdSense ad unit. Requires <AdSenseScript /> to be mounted
 * on the same page. Renders nothing if NEXT_PUBLIC_GOOGLE_ADSENSE_CLIENT_ID
 * is unset or if `slot` is empty (so missing-slot env vars stay invisible).
 */
export function AdUnit({
	slot,
	format = "auto",
	layout,
	layoutKey,
	responsive = true,
	className,
	style,
}: AdUnitProps) {
	const insRef = useRef<HTMLModElement>(null);

	useEffect(() => {
		if (!ADSENSE_CLIENT_ID || !slot) return;
		const el = insRef.current;
		if (!el) return;
		// Guard against duplicate pushes (React StrictMode dev double-invoke,
		// client-side navigation back to this page, or HMR remounts). AdSense
		// sets data-adsbygoogle-status="done" once it has filled a slot.
		if (el.getAttribute("data-adsbygoogle-status")) return;
		try {
			(window.adsbygoogle = window.adsbygoogle || []).push({});
		} catch {
			// AdSense throws if pushed before the script has loaded or on
			// duplicate pushes. The script processes pending pushes when it
			// finishes loading, so we can safely swallow this.
		}
	}, [slot]);

	if (!ADSENSE_CLIENT_ID || !slot) return null;

	return (
		<ins
			ref={insRef}
			className={cn("adsbygoogle block", className)}
			style={{ display: "block", ...style }}
			data-ad-client={ADSENSE_CLIENT_ID}
			data-ad-slot={slot}
			data-ad-format={format}
			data-ad-layout={layout}
			data-ad-layout-key={layoutKey}
			data-full-width-responsive={responsive ? "true" : "false"}
		/>
	);
}
