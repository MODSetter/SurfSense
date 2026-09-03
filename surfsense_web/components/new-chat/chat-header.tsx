"use client";

import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { ImageModelSelector } from "./image-model-selector";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	workspaceId: number;
	className?: string;
	onChatModelSelected?: () => void;
}

export function ChatHeader({ workspaceId, className, onChatModelSelected }: ChatHeaderProps) {
	const isMobile = useIsMobile();
	const selectorClassName = cn(
		className,
		"min-w-0",
		isMobile ? "flex-none basis-auto" : "max-w-[180px] flex-initial shrink"
	);

	return (
		<div
			className={cn(
				"flex min-w-0 items-center justify-end gap-0",
				isMobile ? "w-auto flex-none" : "max-w-[360px] flex-1"
			)}
		>
			<ModelSelector
				workspaceId={workspaceId}
				className={selectorClassName}
				onChatModelSelected={onChatModelSelected}
			/>
			<ImageModelSelector workspaceId={workspaceId} className={selectorClassName} mobileIconOnly />
		</div>
	);
}
