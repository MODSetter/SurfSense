"use client";

import { OctagonAlert, Orbit, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
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
			<div
				className={cn(
					"rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/50 p-4",
					className
				)}
			>
				<div className="flex items-start gap-3">
					<OctagonAlert className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
					<div className="flex-1 space-y-2">
						<p className="text-sm font-medium text-red-800 dark:text-red-200">
							Free token limit reached
						</p>
						<p className="text-xs text-red-600 dark:text-red-300">
							You&apos;ve used all {limit.toLocaleString()} free tokens. Create a free account to
							get 3 million tokens and access to all models.
						</p>
						<Link
							href="/register"
							className="inline-flex items-center gap-1.5 rounded-md bg-linear-to-r from-purple-600 to-blue-600 px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
						>
							<Orbit className="h-4 w-4" />
							Create Free Account
						</Link>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div
			className={cn(
				"rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/50 p-3",
				className
			)}
		>
			<div className="flex items-center gap-3">
				<OctagonAlert className="h-4 w-4 text-amber-500 shrink-0" />
				<p className="flex-1 text-xs text-amber-700 dark:text-amber-300">
					You&apos;ve used {used.toLocaleString()} of {limit.toLocaleString()} free tokens.{" "}
					<Link href="/register" className="font-medium underline hover:no-underline">
						Create an account
					</Link>{" "}
					for 5M free tokens.
				</p>
				<button
					type="button"
					onClick={() => setDismissed(true)}
					className="text-amber-400 hover:text-amber-600 dark:hover:text-amber-200"
				>
					<X className="h-4 w-4" />
				</button>
			</div>
		</div>
	);
}
