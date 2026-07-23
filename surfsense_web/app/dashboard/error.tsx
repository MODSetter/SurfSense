"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { buildIssueUrl } from "@/lib/error-toast";

export default function DashboardError({
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
		<div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
			<h2 className="text-xl font-semibold">Something went wrong</h2>
			<p className="text-muted-foreground max-w-md">
				An error occurred in this section. Your dashboard is still available. If this keeps
				happening, please report it so we can fix it.
			</p>

			{(error.digest || error.code || error.requestId) && (
				<div className="rounded-md border bg-muted/50 px-4 py-2 text-xs text-muted-foreground font-mono max-w-md">
					{error.code && <span>Code: {error.code}</span>}
					{error.requestId && <span className="ml-3">ID: {error.requestId}</span>}
					{error.digest && <span className="ml-3">Digest: {error.digest}</span>}
				</div>
			)}

			<div className="flex gap-2">
				<Button type="button" onClick={reset}>
					Try again
				</Button>
				<Button asChild variant="ghost">
					<Link href="/dashboard">Back to dashboard</Link>
				</Button>
				<Button asChild variant="ghost">
					<a href={issueUrl} target="_blank" rel="noopener noreferrer">
						Report Issue
						<ExternalLink className="h-3.5 w-3.5" />
					</a>
				</Button>
			</div>
		</div>
	);
}
