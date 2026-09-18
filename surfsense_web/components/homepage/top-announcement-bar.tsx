"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Cancel01Icon, LinkSquare02Icon } from "@/components/ui/icons";
import { TOP_ANNOUNCEMENT_ENABLED } from "@/lib/env-config";

// Versioned so a new announcement resurfaces even for visitors who dismissed
// an older one. Bump the version when the announcement changes.
const DISMISS_KEY = "surfsense:top-announcement-dismissed:v1";

/**
 * Top banner pointing visitors at the /sunset announcement.
 *
 * Rendered as the first child of `SiteNav`'s `.ss-home-nav` header rather than
 * as its own sticky element: that header is already `position: sticky`, so
 * stacking the banner inside it makes the two scroll and stick together as
 * one unit instead of each being independently sticky at `top: 0` and
 * overlapping.
 *
 * Uses `--notice`, the blue defined alongside the rest of the palette in
 * `app/(home)/home.css`, with a literal fallback so it also reads correctly
 * on `(home)` routes that have not been moved onto that palette yet.
 *
 * Toggled with `NEXT_PUBLIC_TOP_ANNOUNCEMENT_ENABLED` like `GlobalAnnouncement`,
 * so it can flip on/off from Vercel without a code change. Dismissal is
 * persisted in localStorage so it stays hidden across reloads and navigations.
 */
export function TopAnnouncementBar() {
	// Default visible so the banner is there on first paint instead of popping
	// in after the localStorage check and shifting the nav down. The tradeoff
	// is a visitor who already dismissed it sees a brief flash before this
	// effect hides it again, which is preferable to every other visitor seeing
	// a layout shift on every load.
	const [dismissed, setDismissed] = useState(false);

	useEffect(() => {
		try {
			if (localStorage.getItem(DISMISS_KEY) === "1") {
				setDismissed(true);
			}
		} catch {
			// localStorage can throw in private browsing / when disabled; leave
			// the banner visible.
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

	if (!TOP_ANNOUNCEMENT_ENABLED || dismissed) {
		return null;
	}

	return (
		<div className="w-full">
			{/* Same box as `.ss-home-nav-bar` below it: centered, capped at
			    `--home-max`, bordered on the sides. Filling *this* box with the
			    notice color (rather than the full-bleed strip around it) is what
			    keeps the banner reading as the same width as the nav. */}
			<div className="relative mx-auto flex max-w-(--home-max) items-center justify-center gap-2 border-x border-border bg-(--notice,#3f74c8) px-4 py-2.5 text-center text-sm font-medium text-white">
				<span>SurfSense is moving to a local app.</span>
				<Link
					href="/sunset"
					className="inline-flex items-center gap-1 underline underline-offset-2 hover:opacity-90"
				>
					Read announcement
					<LinkSquare02Icon className="size-3.5" />
				</Link>
				<button
					type="button"
					onClick={handleDismiss}
					aria-label="Dismiss announcement"
					className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[2px] p-1 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
				>
					<Cancel01Icon className="size-4" />
				</button>
			</div>
		</div>
	);
}
