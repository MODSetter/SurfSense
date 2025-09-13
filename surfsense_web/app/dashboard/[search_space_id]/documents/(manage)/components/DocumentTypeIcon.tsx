"use client";

import type React from "react";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

type IconComponent = React.ComponentType<{ size?: number; className?: string }>;

export function getDocumentTypeIcon(type: string): React.ReactNode {
	return getConnectorIcon(type);
}

export function getDocumentTypeLabel(type: string): string {
	return type
		.split("_")
		.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
		.join(" ");
}

export function DocumentTypeChip({ type, className }: { type: string; className?: string }) {
	const icon = getDocumentTypeIcon(type);
	return (
		<span
			className={
				"inline-flex items-center gap-1.5 rounded-full border border-border bg-primary/5 px-2 py-1 text-xs font-medium " +
				(className ?? "")
			}
		>
			<span className="text-primary">{icon}</span>
			{getDocumentTypeLabel(type)}
		</span>
	);
}
