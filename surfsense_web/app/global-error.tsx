"use client";

import "./globals.css";
import posthog from "posthog-js";
import { useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";

const ISSUES_URL = "https://github.com/MODSetter/SurfSense/issues/new";

function buildBasicIssueUrl(error: Error & { digest?: string }) {
	const params = new URLSearchParams();
	const lines = [
		"## Bug Report",
		"",
		"**Describe what happened:**",
		"",
		"",
		"## Diagnostics (auto-filled)",
		"",
		`- **Error:** ${error.message}`,
		...(error.digest ? [`- **Digest:** \`${error.digest}\``] : []),
		`- **Timestamp:** ${new Date().toISOString()}`,
		`- **Page:** \`${typeof window !== "undefined" ? window.location.pathname : "unknown"}\``,
		`- **User Agent:** \`${typeof navigator !== "undefined" ? navigator.userAgent : "unknown"}\``,
	];
	params.set("body", lines.join("\n"));
	params.set("labels", "bug");
	return `${ISSUES_URL}?${params.toString()}`;
}

export default function GlobalError({
	error,
	reset,
}: {
	error: Error & { digest?: string };
	reset: () => void;
}) {
	useEffect(() => {
		posthog.captureException(error);
	}, [error]);

	const issueUrl = useMemo(() => buildBasicIssueUrl(error), [error]);

	return (
		<html lang="en">
			<body>
				<div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
					<h2 className="text-xl font-semibold">Something went wrong</h2>
					<p className="text-sm text-muted-foreground max-w-md">
						An unexpected error occurred. Please try again, or report this issue if it persists.
					</p>

					{error.digest && (
						<p className="text-xs text-muted-foreground font-mono">Digest: {error.digest}</p>
					)}

					<div className="flex gap-2">
						<Button onClick={reset}>Try again</Button>
						<a
							href={issueUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
						>
							Report Issue
						</a>
					</div>
				</div>
			</body>
		</html>
	);
}
