"use client";

import { useEffect } from "react";

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
		<div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
			<h2 className="text-2xl font-semibold">Something went wrong</h2>
			<p className="text-muted-foreground max-w-md">
				An unexpected error occurred. Please try again.
			</p>
			<button
				type="button"
				onClick={reset}
				className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
			>
				Try again
			</button>
		</div>
	);
}
