"use client";

import { ImageModelSelector } from "./image-model-selector";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	workspaceId: number;
	className?: string;
	onChatModelSelected?: () => void;
}

export function ChatHeader({ workspaceId, className, onChatModelSelected }: ChatHeaderProps) {
	return (
		<div className="flex min-w-0 shrink-0 items-center gap-2">
			<ModelSelector
				workspaceId={workspaceId}
				className={className}
				onChatModelSelected={onChatModelSelected}
			/>
			<ImageModelSelector workspaceId={workspaceId} className={className} mobileIconOnly />
		</div>
	);
}
