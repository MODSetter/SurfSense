"use client";

import { cn } from "@/lib/utils";
import { ImageModelSelector } from "./image-model-selector";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	workspaceId: number;
	className?: string;
	onChatModelSelected?: () => void;
}

export function ChatHeader({ workspaceId, className, onChatModelSelected }: ChatHeaderProps) {
	const selectorClassName = cn(className, "min-w-0 max-w-[180px] basis-0 flex-1");

	return (
		<div className="flex min-w-0 max-w-[360px] flex-1 items-center justify-end gap-0">
			<ModelSelector
				workspaceId={workspaceId}
				className={selectorClassName}
				onChatModelSelected={onChatModelSelected}
			/>
			<ImageModelSelector workspaceId={workspaceId} className={selectorClassName} mobileIconOnly />
		</div>
	);
}
