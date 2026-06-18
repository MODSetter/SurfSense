"use client";

import { ImageModelSelector } from "./image-model-selector";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
	className?: string;
	onChatModelSelected?: () => void;
}

export function ChatHeader({ searchSpaceId, className, onChatModelSelected }: ChatHeaderProps) {
	return (
		<div className="flex items-center gap-2">
			<ModelSelector
				searchSpaceId={searchSpaceId}
				className={className}
				onChatModelSelected={onChatModelSelected}
			/>
			<ImageModelSelector searchSpaceId={searchSpaceId} className={className} />
		</div>
	);
}
