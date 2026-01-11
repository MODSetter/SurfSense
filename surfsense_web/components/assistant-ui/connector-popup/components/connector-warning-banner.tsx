"use client";

import { AlertTriangle, X } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface ConnectorWarningBannerProps {
	warning: string;
	statusMessage?: string | null;
	onDismiss?: () => void;
	className?: string;
}

export const ConnectorWarningBanner: FC<ConnectorWarningBannerProps> = ({
	warning,
	statusMessage,
	onDismiss,
	className,
}) => {
	const [isDismissed, setIsDismissed] = useState(false);

	if (isDismissed) return null;

	const handleDismiss = () => {
		setIsDismissed(true);
		onDismiss?.();
	};

	return (
		<div
			className={cn(
				"flex items-start gap-3 p-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 dark:bg-yellow-500/5 mb-4",
				className
			)}
		>
			<AlertTriangle className="size-4 text-yellow-600 dark:text-yellow-500 shrink-0 mt-0.5" />
			<div className="flex-1 min-w-0">
				<p className="text-[12px] font-medium text-yellow-900 dark:text-yellow-200">{warning}</p>
				{statusMessage && (
					<p className="text-[11px] text-yellow-700 dark:text-yellow-300 mt-1">{statusMessage}</p>
				)}
			</div>
			{onDismiss && (
				<button
					type="button"
					onClick={handleDismiss}
					className="shrink-0 p-0.5 rounded hover:bg-yellow-500/20 transition-colors"
					aria-label="Dismiss warning"
				>
					<X className="size-3.5 text-yellow-700 dark:text-yellow-300" />
				</button>
			)}
		</div>
	);
};
