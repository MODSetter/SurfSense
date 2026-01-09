"use client";

import { AlertTriangle, Ban, Wrench } from "lucide-react";
import type { FC } from "react";
import type { ConnectorStatus } from "../config/connector-status-config";
import { cn } from "@/lib/utils";

interface ConnectorStatusBadgeProps {
	status: ConnectorStatus;
	className?: string;
}

export const ConnectorStatusBadge: FC<ConnectorStatusBadgeProps> = ({ status, className }) => {
	if (status === "active") {
		return null;
	}

	const getBadgeConfig = () => {
		switch (status) {
			case "warning":
				return {
					icon: AlertTriangle,
					className: "text-yellow-500 dark:text-yellow-400",
					title: "Warning",
				};
			case "disabled":
				return {
					icon: Ban,
					className: "text-red-500 dark:text-red-400",
					title: "Disabled",
				};
			case "maintenance":
				return {
					icon: Wrench,
					className: "text-orange-500 dark:text-orange-400",
					title: "Maintenance",
				};
			case "deprecated":
				return {
					icon: AlertTriangle,
					className: "text-amber-500 dark:text-amber-400",
					title: "Deprecated",
				};
			default:
				return null;
		}
	};

	const config = getBadgeConfig();
	if (!config) return null;

	const Icon = config.icon;

	return (
		<div
			className={cn("flex items-center justify-center shrink-0", className)}
			title={config.title}
		>
			<Icon className={cn("size-3.5", config.className)} />
		</div>
	);
};
