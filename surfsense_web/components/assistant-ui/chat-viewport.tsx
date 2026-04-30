"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { ArrowDownIcon } from "lucide-react";
import type { FC, ReactNode } from "react";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

const ChatScrollToBottom: FC = () => (
	<ThreadPrimitive.ScrollToBottom asChild>
		<TooltipIconButton
			tooltip="Scroll to bottom"
			variant="outline"
			className="aui-thread-scroll-to-bottom -top-12 absolute z-10 self-center rounded-full p-4 disabled:invisible dark:bg-main-panel dark:hover:bg-accent"
		>
			<ArrowDownIcon />
		</TooltipIconButton>
	</ThreadPrimitive.ScrollToBottom>
);

export interface ChatViewportProps {
	children: ReactNode;
	footer?: ReactNode;
}

export const ChatViewport: FC<ChatViewportProps> = ({ children, footer }) => (
	<ThreadPrimitive.Viewport
		scrollToBottomOnRunStart
		scrollToBottomOnInitialize
		scrollToBottomOnThreadSwitch
		className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 pt-4"
		style={{ scrollbarGutter: "stable" }}
	>
		{children}
		{footer ? (
			<ThreadPrimitive.ViewportFooter
				className="aui-thread-viewport-footer sticky bottom-0 z-10 mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-3xl bg-main-panel pb-4 md:pb-6"
				style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
			>
				<ChatScrollToBottom />
				{footer}
			</ThreadPrimitive.ViewportFooter>
		) : null}
	</ThreadPrimitive.Viewport>
);
