"use client";

import { ArrowUpRight, Info, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { bannerPlacement } from "./banner-placement";

const ANNOUNCEMENT_URL =
	"https://www.surfsense.com/announcements/2026-09-18-surfsense-2-desktop-app";

const DISMISSED_KEY = "surfsense-desktop-app-banner-dismissed";

// Read by the `h-app-screen` / `min-h-app-screen` utilities in globals.css, so
// full-height pages shrink by the banner instead of running off the screen.
// globals.css gives it the one-line height from the first paint; this corrects
// it when the text wraps.
const HEIGHT_VARIABLE = "--app-banner-height";

function readDismissed(): boolean {
	try {
		return localStorage.getItem(DISMISSED_KEY) === "1";
	} catch {
		return false;
	}
}

/** Top-of-page notice pointing self-hosted users to the SurfSense 2.0 desktop app. */
export function DesktopAppBanner() {
	const t = useTranslations("desktop_app_banner");
	const placement = bannerPlacement(usePathname() ?? "/");
	const ref = useRef<HTMLElement>(null);
	// Unknown until mounted: localStorage is client-only, and showing then hiding
	// the banner would shift the page for everyone who dismissed it.
	const [dismissed, setDismissed] = useState<boolean | null>(null);

	useEffect(() => {
		setDismissed(readDismissed());
	}, []);

	const visible = placement === "fixed" || (placement === "dismissible" && dismissed === false);

	useEffect(() => {
		const root = document.documentElement;
		const node = ref.current;
		if (!visible || !node) {
			root.style.removeProperty(HEIGHT_VARIABLE);
			return;
		}
		const observer = new ResizeObserver(() => {
			root.style.setProperty(HEIGHT_VARIABLE, `${node.offsetHeight}px`);
		});
		observer.observe(node);
		return () => {
			observer.disconnect();
			root.style.removeProperty(HEIGHT_VARIABLE);
		};
	}, [visible]);

	if (!visible) return null;

	const dismiss = () => {
		try {
			localStorage.setItem(DISMISSED_KEY, "1");
		} catch {
			// Storage unavailable: hide it for this page view only.
		}
		setDismissed(true);
	};

	return (
		<section
			ref={ref}
			data-app-banner=""
			aria-label={t("label")}
			className="relative flex items-center justify-center gap-2 border-b bg-muted px-10 py-2 text-center text-sm text-foreground"
		>
			<Info className="size-4 shrink-0 text-muted-foreground" aria-hidden />
			<p className="text-pretty">
				<span className="max-md:hidden">{t("message")} </span>
				<span className="md:hidden">{t("message_short")} </span>
				<a
					href={ANNOUNCEMENT_URL}
					target="_blank"
					rel="noopener noreferrer"
					// On phones the link's hit area stretches over the whole banner.
					className="inline-flex items-center gap-0.5 align-middle font-medium underline underline-offset-4 hover:text-primary max-md:after:absolute max-md:after:inset-0"
				>
					{/* Phones show only the arrow: the whole banner is the link there. */}
					<span className="max-md:sr-only">{t("link")}</span>
					<ArrowUpRight className="size-4 shrink-0" aria-hidden />
				</a>
			</p>
			{placement === "dismissible" && (
				<Button
					type="button"
					variant="ghost"
					size="icon"
					onClick={dismiss}
					aria-label={t("dismiss")}
					className="absolute top-1/2 right-2 z-10 size-7 -translate-y-1/2 text-muted-foreground"
				>
					<X className="size-4" />
				</Button>
			)}
		</section>
	);
}
