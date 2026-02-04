"use client";

import type React from "react";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function getDocumentTypeIcon(type: string): React.ReactNode {
	return getConnectorIcon(type);
}

export function getDocumentTypeLabel(type: string): string {
	return type
		.split("_")
		.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
		.join(" ");
}

const MAX_LABEL_LENGTH = 28;

export function DocumentTypeChip({ type, className }: { type: string; className?: string }) {
	const icon = getDocumentTypeIcon(type);
	const fullLabel = getDocumentTypeLabel(type);
	const truncatedLabel = fullLabel.length > MAX_LABEL_LENGTH 
		? `${fullLabel.slice(0, MAX_LABEL_LENGTH)}...` 
		: fullLabel;
	const needsTruncation = fullLabel.length > MAX_LABEL_LENGTH;

	const chip = (
		<span
			className={`inline-flex items-center gap-1.5 rounded-md border border-border/50 bg-muted/30 px-2 py-0.5 text-xs font-medium text-muted-foreground ${className ?? ""}`}
		>
			<span className="opacity-70 flex-shrink-0">{icon}</span>
			<span className="truncate">{truncatedLabel}</span>
		</span>
	);

	if (needsTruncation) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>{chip}</TooltipTrigger>
				<TooltipContent side="top" className="max-w-xs">
					<p>{fullLabel}</p>
				</TooltipContent>
			</Tooltip>
		);
	}

	return chip;
}
