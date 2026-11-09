"use client";

import { useEffect } from "react";
import { HomeButton } from "@/components/site/home-button";

export default function ErrorPage({
	error,
	reset,
}: {
	error: globalThis.Error & { digest?: string };
	reset: () => void;
}) {
	useEffect(() => {
		import("posthog-js")
			.then(({ default: posthog }) => {
				posthog.captureException(error);
			})
			.catch(() => {});
	}, [error]);

	return (
		<div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center px-4">
			<h2 className="text-2xl font-semibold">Something went wrong</h2>
			<p className="text-muted-foreground max-w-md">
				An unexpected error occurred. Please try again.
			</p>

			{error.digest && (
				<div className="rounded-md border bg-muted/50 px-4 py-2 text-xs text-muted-foreground font-mono max-w-md">
					Digest: {error.digest}
				</div>
			)}

			<HomeButton type="button" size="lg" onClick={reset}>
				Try again
			</HomeButton>
		</div>
	);
}
