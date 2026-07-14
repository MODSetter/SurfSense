import { useAuiState } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import type { FC } from "react";
import { showMessageTimestampsAtom } from "@/atoms/chat/show-timestamps.atom";
import { formatMessageTimestamp } from "@/lib/format-date";
import { cn } from "@/lib/utils";

/**
 * Muted, always-visible timestamp under a chat message. Renders only when the
 * user has opted in via {@link showMessageTimestampsAtom} and the message
 * carries a ``createdAt`` (absent on optimistic pre-persist messages).
 */
export const MessageTimestamp: FC<{ className?: string }> = ({ className }) => {
	const show = useAtomValue(showMessageTimestampsAtom);
	const createdAt = useAuiState(({ message }) => message?.createdAt);

	if (!show || !createdAt) return null;

	return (
		<div className={cn("select-none text-[11px] text-muted-foreground", className)}>
			{formatMessageTimestamp(createdAt)}
		</div>
	);
};
