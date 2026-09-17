"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { HomeButton } from "@/components/homepage/home/home-button";
import { Spinner } from "@/components/ui/spinner";
import { useSession } from "@/hooks/use-session";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { redirectToLogin } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";

/**
 * Rendered inline in the hero on `/sunset` rather than as its own section —
 * a page whose entire purpose is one export button doesn't need a second
 * ruled band beneath the headline. Built from the same `ss-home-*` primitives
 * as the rest of the site design (`HomeButton` rather than the product's own
 * `Button`) so it still reads as part of the same document as the homepage,
 * pricing and contact pages.
 */

const FALLBACK_FILENAME = "surfsense-export.zip";
const DISPOSITION_FILENAME = /filename\*?=(?:UTF-8'')?"?([^";]+)/i;

export function filenameFromDisposition(header: string | null): string {
	if (!header) return FALLBACK_FILENAME;
	const match = header.match(DISPOSITION_FILENAME);
	const name = match?.[1]?.trim();
	return name || FALLBACK_FILENAME;
}

function triggerDownload(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

export function SunsetExport() {
	const session = useSession();
	const [isExporting, setIsExporting] = useState(false);

	// Session status resolves asynchronously and can settle before hydration
	// finishes, so deriving `disabled`/label straight from it made the first
	// client render disagree with the server-rendered HTML. Gating on mount
	// keeps the initial paint identical on both sides; the real state takes
	// over a tick later.
	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);

	async function handleExport() {
		if (isExporting) return;
		if (session.status !== "authenticated") {
			redirectToLogin();
			return;
		}

		setIsExporting(true);
		try {
			const response = await authenticatedFetch(buildBackendUrl("/api/v1/export"), {
				method: "GET",
				skipAuthRedirect: true,
			});
			if (response.status === 401) {
				redirectToLogin();
				return;
			}
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
				throw new Error(typeof errorData.detail === "string" ? errorData.detail : "Export failed");
			}

			const blob = await response.blob();
			triggerDownload(blob, filenameFromDisposition(response.headers.get("Content-Disposition")));

			const skipped = response.headers.get("X-Skipped-Documents");
			toast.success(
				skipped
					? `Account exported. ${skipped} document${skipped === "1" ? "" : "s"} skipped.`
					: "Account exported"
			);
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Export failed");
		} finally {
			setIsExporting(false);
		}
	}

	const sessionLoading = session.status === "loading";
	const busy = mounted && (sessionLoading || isExporting);
	const signedIn = mounted && session.status === "authenticated";

	return (
		<div className="mt-10 flex flex-col items-center">
			<HomeButton
				type="button"
				size="xl"
				disabled={busy}
				onClick={() => void handleExport()}
				className="relative w-fit shrink-0"
			>
				<span className={busy ? "opacity-0" : ""}>
					{signedIn ? "Export account" : "Sign in to export"}
				</span>
				{busy ? <Spinner size="sm" className="absolute" /> : null}
			</HomeButton>
			<p className="ss-home-body mx-auto mt-4 max-w-md text-sm text-pretty">
				<span className="font-medium">Note:</span> Downloads every workspace you can access: ready
				documents as markdown, folder structure, and chat threads. Original uploads, generated
				artifacts, tool calls, agent steps, and live citation links are not included.
			</p>
		</div>
	);
}
