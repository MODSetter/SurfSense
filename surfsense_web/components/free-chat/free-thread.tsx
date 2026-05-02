"use client";

import { AuiIf, ThreadPrimitive } from "@assistant-ui/react";
import type { FC } from "react";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { ChatViewport } from "@/components/assistant-ui/chat-viewport";
import { EditComposer } from "@/components/assistant-ui/edit-composer";
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

export const FreeThread: FC = () => {
	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-main-panel"
			style={{
				["--thread-max-width" as string]: "44rem",
			}}
		>
			<ChatViewport
				footer={
					<AuiIf condition={({ thread }) => !thread.isEmpty}>
						<FreeComposer />
					</AuiIf>
				}
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
			</ChatViewport>
		</ThreadPrimitive.Root>
	);
};
