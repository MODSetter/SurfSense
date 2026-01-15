"use client";

import { AlertTriangle, Ban, Wrench } from "lucide-react";
import type { FC } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ConnectorStatus } from "../config/connector-status-config";

interface ConnectorStatusBadgeProps {
	status: ConnectorStatus;
	statusMessage?: string | null;
	className?: string;
}

export const ConnectorStatusBadge: FC<ConnectorStatusBadgeProps> = ({
	status,
	statusMessage,
	className,
}) => {
	if (status === "active") {
		return null;
	}

	const getBadgeConfig = () => {
		switch (status) {
			case "warning":
				return {
					icon: AlertTriangle,
					className: "text-yellow-500 dark:text-yellow-400",
					defaultTitle: "Warning",
				};
			case "disabled":
				return {
					icon: Ban,
					className: "text-red-500 dark:text-red-400",
					defaultTitle: "Disabled",
				};
			case "maintenance":
				return {
					icon: Wrench,
					className: "text-orange-500 dark:text-orange-400",
					defaultTitle: "Maintenance",
				};
			case "deprecated":
				return {
					icon: AlertTriangle,
					className: "text-slate-500 dark:text-slate-400",
					defaultTitle: "Deprecated",
				};
			default:
				return null;
		}
	};

	const config = getBadgeConfig();
	if (!config) return null;

	const Icon = config.icon;
	// Show statusMessage in tooltip for warning, deprecated, disabled, and maintenance statuses
	const shouldUseTooltip =
		(status === "warning" ||
			status === "deprecated" ||
			status === "disabled" ||
			status === "maintenance") &&
		statusMessage;
	const tooltipTitle = shouldUseTooltip ? statusMessage : config.defaultTitle;

	// Use Tooltip component for statuses with statusMessage, native title for others
	if (shouldUseTooltip) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>
					<span className={cn("inline-flex items-center justify-center shrink-0", className)}>
						<Icon className={cn("size-3.5", config.className)} />
					</span>
				</TooltipTrigger>
				<TooltipContent side="top" className="max-w-xs">
					{statusMessage}
				</TooltipContent>
			</Tooltip>
		);
	}

	return (
		<span
			className={cn("inline-flex items-center justify-center shrink-0", className)}
			title={tooltipTitle}
		>
			<Icon className={cn("size-3.5", config.className)} />
		</span>
	);
};
