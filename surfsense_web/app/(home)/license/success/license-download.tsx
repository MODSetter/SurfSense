"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { HomeButton } from "@/components/homepage/home/home-button";
import { Spinner } from "@/components/ui/spinner";
import { buildBackendUrl } from "@/lib/env-config";

const LICENSE_FILENAME = "surfsense.lic";

type State = "idle" | "loading" | "ready" | "missing" | "error";

function triggerDownload(text: string) {
	const blob = new Blob([text], { type: "text/plain" });
	const url = URL.createObjectURL(blob);
	const anchor = document.createElement("a");
	anchor.href = url;
	anchor.download = LICENSE_FILENAME;
	document.body.appendChild(anchor);
	anchor.click();
	anchor.remove();
	URL.revokeObjectURL(url);
}

/**
 * This page is the reliable delivery path, not the email: it serves the file
 * straight from the checkout session, so it works even when the buyer mistyped
 * their address and the email goes nowhere.
 */
export function LicenseDownload() {
	const sessionId = useSearchParams().get("session_id");
	const [state, setState] = useState<State>("idle");
	const autoDownloaded = useRef(false);

	const fetchLicense = useCallback(async (): Promise<string | null> => {
		if (!sessionId) return null;
		const response = await fetch(
			buildBackendUrl("/api/v1/license/file", { session_id: sessionId })
		);
		if (response.status === 404) {
			setState("missing");
			return null;
		}
		if (!response.ok) {
			setState("error");
			return null;
		}
		return response.text();
	}, [sessionId]);

	const download = useCallback(async () => {
		setState("loading");
		try {
			const certificate = await fetchLicense();
			if (certificate === null) return;
			triggerDownload(certificate);
			setState("ready");
		} catch {
			setState("error");
		}
	}, [fetchLicense]);

	useEffect(() => {
		// The webhook can lag the redirect by 30s, so the first attempt may be
		// what actually creates the license. Try once on mount, then leave it to
		// the button so a slow webhook does not become a retry loop.
		if (!sessionId || autoDownloaded.current) return;
		autoDownloaded.current = true;
		void download();
	}, [sessionId, download]);

	if (!sessionId) {
		return (
			<p className="text-sm text-destructive">
				This link is missing its checkout reference. Use the copy we emailed you, or request it
				again at{" "}
				<a className="ss-home-link" href="/license">
					surfsense.com/license
				</a>
				.
			</p>
		);
	}

	return (
		<div className="flex flex-col gap-3">
			<HomeButton onClick={download} disabled={state === "loading"} className="self-start">
				{state === "loading" ? <Spinner size="sm" /> : null}
				{state === "loading" ? "Preparing" : "Download license file"}
			</HomeButton>
			{state === "ready" ? (
				<p className="ss-home-body text-sm">
					Saved as <code className="ss-home-mono">{LICENSE_FILENAME}</code>. A copy is on its way to
					your email as well.
				</p>
			) : null}
			{state === "missing" ? (
				<p className="text-sm text-destructive">
					We cannot find a license for this checkout yet. Payment can take a moment to settle, so
					wait a few seconds and press the button again. If it keeps failing, contact support with
					your payment details.
				</p>
			) : null}
			{state === "error" ? (
				<p className="text-sm text-destructive">
					Something went wrong preparing your file. Press the button to try again, or request it at{" "}
					<a className="ss-home-link" href="/license">
						surfsense.com/license
					</a>
					.
				</p>
			) : null}
		</div>
	);
}
