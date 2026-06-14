"use client";

import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
	className?: string;
}

export function ChatHeader({ searchSpaceId, className }: ChatHeaderProps) {
	return (
		<div className="flex items-center gap-2">
			<ModelSelector searchSpaceId={searchSpaceId} className={className} />
		</div>
	);
}
