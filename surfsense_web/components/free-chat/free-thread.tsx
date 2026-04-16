"use client";

import { AuiIf, ThreadPrimitive } from "@assistant-ui/react";
import { ArrowDownIcon } from "lucide-react";
import type { FC } from "react";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { EditComposer } from "@/components/assistant-ui/edit-composer";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { UserMessage } from "@/components/assistant-ui/user-message";
import { FreeComposer } from "./free-composer";

const FreeThreadWelcome: FC = () => {
	return (
		<div className="aui-thread-welcome-root mx-auto flex w-full max-w-(--thread-max-width) grow flex-col items-center px-4 relative">
			<div className="aui-thread-welcome-message absolute bottom-[calc(50%+5rem)] left-0 right-0 flex flex-col items-center text-center">
				<h1 className="aui-thread-welcome-message-inner text-3xl md:text-5xl select-none">
					What can I help with?
				</h1>
			</div>
			<div className="w-full flex items-start justify-center absolute top-[calc(50%-3.5rem)] left-0 right-0">
				<FreeComposer />
			</div>
		</div>
	);
};

const ThreadScrollToBottom: FC = () => {
	return (
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
};

export const FreeThread: FC = () => {
	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-main-panel"
			style={{
				["--thread-max-width" as string]: "44rem",
			}}
		>
			<ThreadPrimitive.Viewport
				turnAnchor="top"
				className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 pt-4"
				style={{ scrollbarGutter: "stable" }}
			>
				<AuiIf condition={({ thread }) => thread.isEmpty}>
					<FreeThreadWelcome />
				</AuiIf>

				<ThreadPrimitive.Messages
					components={{
						UserMessage,
						EditComposer,
						AssistantMessage,
					}}
				/>

				<AuiIf condition={({ thread }) => !thread.isEmpty}>
					<div className="grow" />
				</AuiIf>

				<ThreadPrimitive.ViewportFooter
					className="aui-thread-viewport-footer sticky bottom-0 z-10 mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-3xl bg-main-panel pb-4 md:pb-6"
					style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
				>
					<ThreadScrollToBottom />
					<AuiIf condition={({ thread }) => !thread.isEmpty}>
						<FreeComposer />
					</AuiIf>
				</ThreadPrimitive.ViewportFooter>
			</ThreadPrimitive.Viewport>
		</ThreadPrimitive.Root>
	);
};
