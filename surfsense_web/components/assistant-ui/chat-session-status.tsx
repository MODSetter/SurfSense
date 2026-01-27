"use client";

import type { FC } from "react";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface ChatSessionStatusProps {
	isAiResponding: boolean;
	respondingToUserId: string | null;
	currentUserId: string | null;
	members: Array<{
		user_id: string;
		user_display_name?: string | null;
		user_email?: string | null;
	}>;
	className?: string;
}

export const ChatSessionStatus: FC<ChatSessionStatusProps> = ({
	isAiResponding,
	respondingToUserId,
	currentUserId,
	members,
	className,
}) => {
	if (!isAiResponding || !respondingToUserId) {
		return null;
	}

	if (respondingToUserId === currentUserId) {
		return null;
	}

	const respondingUser = members.find((m) => m.user_id === respondingToUserId);
	const displayName =
		respondingUser?.user_display_name || respondingUser?.user_email || "another user";

	return (
		<div
			className={cn(
				"flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground bg-muted/50 rounded-lg",
				"animate-in fade-in slide-in-from-bottom-2 duration-300 ease-out",
				className
			)}
		>
			<Spinner size="xs" />
			<span>Currently responding to {displayName}</span>
		</div>
	);
};
