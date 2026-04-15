"use client";

import { ExternalLink } from "lucide-react";
import { useEffect, useMemo } from "react";
import { buildIssueUrl } from "@/lib/error-toast";

export default function ErrorPage({
	error,
	reset,
}: {
	error: globalThis.Error & { digest?: string; code?: string; requestId?: string };
	reset: () => void;
}) {
	useEffect(() => {
		import("posthog-js")
			.then(({ default: posthog }) => {
				posthog.captureException(error);
			})
			.catch(() => {});
	}, [error]);

	const issueUrl = useMemo(() => buildIssueUrl(error), [error]);

	return (
		<div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center px-4">
			<h2 className="text-2xl font-semibold">Something went wrong</h2>
			<p className="text-muted-foreground max-w-md">
				An unexpected error occurred. Please try again, or report this issue if it persists.
			</p>

			{(error.digest || error.code || error.requestId) && (
				<div className="rounded-md border bg-muted/50 px-4 py-2 text-xs text-muted-foreground font-mono max-w-md">
					{error.code && <span>Code: {error.code}</span>}
					{error.requestId && <span className="ml-3">ID: {error.requestId}</span>}
					{error.digest && <span className="ml-3">Digest: {error.digest}</span>}
				</div>
			)}

			<div className="flex gap-2">
				<button
					type="button"
					onClick={reset}
					className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
				>
					Try again
				</button>
				<a
					href={issueUrl}
					target="_blank"
					rel="noopener noreferrer"
					className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
				>
					<ExternalLink className="h-3.5 w-3.5" />
					Report Issue
				</a>
			</div>
		</div>
	);
}
