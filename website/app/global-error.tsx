"use client";

import "./globals.css";
import posthog from "posthog-js";
import { useEffect } from "react";
import { HomeButton } from "@/components/site/home-button";

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

	return (
		<html lang="en">
			<body>
				<div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
					<h2 className="text-xl font-semibold">Something went wrong</h2>
					<p className="text-sm text-muted-foreground max-w-md">
						An unexpected error occurred. Please try again.
					</p>

					{error.digest && (
						<p className="text-xs text-muted-foreground font-mono">Digest: {error.digest}</p>
					)}

					<HomeButton type="button" size="lg" onClick={reset}>
						Try again
					</HomeButton>
				</div>
			</body>
		</html>
	);
}
