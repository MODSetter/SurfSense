"use client";

import { Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_ADSENSE_CLIENT_ID;

// Versioned key so the copy can change later without resurfacing for users who
// already dismissed an older variant (bump the version to re-show).
const DISMISS_KEY = "surfsense:remove-ads-banner-dismissed:v1";

/**
 * Dismissible promo shown on the free /free/[model_slug] chat pages, nudging
 * anonymous users to sign up to remove ads. Dismissal is persisted in
 * localStorage so it stays hidden across reloads and navigations. The free
 * chat keeps working whether or not the banner is dismissed.
 *
 * Renders nothing when AdSense is not configured (dev/preview), since there are
 * no ads to remove in that case.
 */
export function RemoveAdsBanner({ className }: { className?: string }) {
	// Default hidden so dismissed users never see a flash before the stored
	// value is read on the client (avoids a hydration/flicker mismatch).
	const [dismissed, setDismissed] = useState(true);

	useEffect(() => {
		try {
			setDismissed(localStorage.getItem(DISMISS_KEY) === "1");
		} catch {
			// localStorage can throw in private browsing / when disabled.
			setDismissed(false);
		}
	}, []);

	const handleDismiss = () => {
		setDismissed(true);
		try {
			localStorage.setItem(DISMISS_KEY, "1");
		} catch {
			// Ignore: dismissal just won't persist across reloads.
		}
	};

	if (!ADSENSE_CLIENT_ID || dismissed) return null;

	return (
		<div className={cn("shrink-0 border-b bg-muted/30 px-4 py-3", className)}>
			<Alert className="relative mx-auto w-full max-w-2xl pr-10">
				<Sparkles />
				<AlertTitle>Go ad-free with a free account</AlertTitle>
				<AlertDescription>
					<p>
						Create a free SurfSense account to remove ads, unlock $5 of premium credit, and save
						your chat history. You can keep chatting for free either way.
					</p>
					<Button asChild size="sm" className="mt-1">
						<Link href="/login">Create Free Account</Link>
					</Button>
				</AlertDescription>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					onClick={handleDismiss}
					aria-label="Dismiss"
					className="absolute top-2 right-2 size-6"
				>
					<X />
				</Button>
			</Alert>
		</div>
	);
}
