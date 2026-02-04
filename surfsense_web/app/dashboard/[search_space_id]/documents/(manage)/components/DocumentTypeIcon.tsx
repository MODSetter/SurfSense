"use client";

import type React from "react";
import { useRef, useState, useEffect } from "react";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function getDocumentTypeIcon(type: string, className?: string): React.ReactNode {
	return getConnectorIcon(type, className);
}

export function getDocumentTypeLabel(type: string): string {
	return type
		.split("_")
		.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
		.join(" ");
}

export function DocumentTypeChip({ type, className }: { type: string; className?: string }) {
	const icon = getDocumentTypeIcon(type, "h-4 w-4");
	const fullLabel = getDocumentTypeLabel(type);
	const textRef = useRef<HTMLSpanElement>(null);
	const [isTruncated, setIsTruncated] = useState(false);

	useEffect(() => {
		const checkTruncation = () => {
			if (textRef.current) {
				setIsTruncated(textRef.current.scrollWidth > textRef.current.clientWidth);
			}
		};
		checkTruncation();
		window.addEventListener("resize", checkTruncation);
		return () => window.removeEventListener("resize", checkTruncation);
	}, []);

	const chip = (
		<span
			className={`inline-flex items-center gap-1.5 rounded bg-muted/40 px-2 py-1 text-xs text-muted-foreground max-w-full overflow-hidden ${className ?? ""}`}
		>
			<span className="opacity-80 flex-shrink-0">{icon}</span>
			<span ref={textRef} className="truncate min-w-0">{fullLabel}</span>
		</span>
	);

	if (isTruncated) {
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
