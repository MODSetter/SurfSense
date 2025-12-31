import { AssistantIf, ThreadPrimitive } from "@assistant-ui/react";
import type { FC } from "react";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";
import { ThinkingStepsContext } from "@/components/assistant-ui/thinking-steps";
import { ThreadWelcome } from "@/components/assistant-ui/thread-welcome";
import { Composer } from "@/components/assistant-ui/composer";
import { ThreadScrollToBottom } from "@/components/assistant-ui/thread-scroll-to-bottom";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { UserMessage } from "@/components/assistant-ui/user-message";
import { EditComposer } from "@/components/assistant-ui/edit-composer";

/**
 * Props for the Thread component
 */
interface ThreadProps {
	messageThinkingSteps?: Map<string, ThinkingStep[]>;
	/** Optional header component to render at the top of the viewport (sticky) */
	header?: React.ReactNode;
}

export const Thread: FC<ThreadProps> = ({ messageThinkingSteps = new Map(), header }) => {
	return (
		<ThinkingStepsContext.Provider value={messageThinkingSteps}>
			<ThreadPrimitive.Root
				className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-background"
				style={{
					["--thread-max-width" as string]: "44rem",
				}}
			>
				<ThreadPrimitive.Viewport
					turnAnchor="top"
					className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 pt-4"
				>
					{/* Optional sticky header for model selector etc. */}
					{header && <div className="sticky top-0 z-10 mb-4">{header}</div>}

					<AssistantIf condition={({ thread }) => thread.isEmpty}>
						<ThreadWelcome />
					</AssistantIf>

					<ThreadPrimitive.Messages
						components={{
							UserMessage,
							EditComposer,
							AssistantMessage,
						}}
					/>

					<ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-3xl bg-background pb-4 md:pb-6">
						<ThreadScrollToBottom />
						<AssistantIf condition={({ thread }) => !thread.isEmpty}>
							<div className="fade-in slide-in-from-bottom-4 animate-in duration-500 ease-out fill-mode-both">
								<Composer />
							</div>
						</AssistantIf>
					</ThreadPrimitive.ViewportFooter>
				</ThreadPrimitive.Viewport>
			</ThreadPrimitive.Root>
		</ThinkingStepsContext.Provider>
	);
};
