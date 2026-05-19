"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { ArrowDownIcon } from "lucide-react";
import type { FC, ReactNode } from "react";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

const ChatScrollToBottom: FC = () => (
	<ThreadPrimitive.ScrollToBottom asChild>
		<TooltipIconButton
			tooltip="Scroll to bottom"
			className="aui-thread-scroll-to-bottom -top-12 absolute z-10 self-center rounded-full border-0 bg-muted p-4 text-foreground hover:bg-accent hover:text-accent-foreground disabled:invisible"
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
		turnAnchor="top"
		autoScroll
		scrollToBottomOnRunStart
		scrollToBottomOnInitialize
		scrollToBottomOnThreadSwitch
		className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 scroll-smooth"
		style={{ scrollbarGutter: "stable" }}
	>
		<div
			aria-hidden
			className="aui-chat-viewport-top-fade pointer-events-none sticky top-0 z-10 -mx-4 h-2 shrink-0 bg-gradient-to-b from-main-panel from-20% to-transparent"
		/>
		{children}
		{footer ? (
			<ThreadPrimitive.ViewportFooter
				className="aui-chat-composer-footer sticky bottom-0 z-20 -mx-4 mt-auto flex flex-col items-stretch bg-gradient-to-t from-main-panel from-60% to-transparent px-4 pt-6"
				style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
			>
				<div className="aui-chat-composer-area relative mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-3 overflow-visible">
					<ChatScrollToBottom />
					{footer}
				</div>
			</ThreadPrimitive.ViewportFooter>
		) : null}
	</ThreadPrimitive.Viewport>
);
