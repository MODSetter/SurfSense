"use client";

import { OctagonAlert, Orbit, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface QuotaWarningBannerProps {
	used: number;
	limit: number;
	warningThreshold: number;
	className?: string;
}

export function QuotaWarningBanner({
	used,
	limit,
	warningThreshold,
	className,
}: QuotaWarningBannerProps) {
	const [dismissed, setDismissed] = useState(false);
	const isWarning = used >= warningThreshold && used < limit;
	const isExceeded = used >= limit;

	if (dismissed || (!isWarning && !isExceeded)) return null;

	if (isExceeded) {
		return (
			<Alert variant="destructive" className={className}>
				<OctagonAlert />
				<AlertTitle>Free token limit reached</AlertTitle>
				<AlertDescription>
					<p>
						You&apos;ve used all {limit.toLocaleString()} free tokens. Create a free account to get
						$5 of premium credit and access to all models.
					</p>
					<Button asChild size="sm" className="mt-1">
						<Link href="/register">
							<Orbit data-icon="inline-start" />
							Create Free Account
						</Link>
					</Button>
				</AlertDescription>
			</Alert>
		);
	}

	return (
		<Alert variant="warning" className={cn("pr-10", className)}>
			<OctagonAlert />
			<AlertTitle>Running low on free tokens</AlertTitle>
			<AlertDescription>
				You&apos;ve used {used.toLocaleString()} of {limit.toLocaleString()} free tokens.{" "}
				<Link href="/register" className="font-medium underline hover:no-underline">
					Create an account
				</Link>{" "}
				for $5 of premium credit.
			</AlertDescription>
			<Button
				type="button"
				variant="ghost"
				size="icon"
				onClick={() => setDismissed(true)}
				aria-label="Dismiss"
				className="absolute top-2 right-2 size-6"
			>
				<X />
			</Button>
		</Alert>
	);
}
