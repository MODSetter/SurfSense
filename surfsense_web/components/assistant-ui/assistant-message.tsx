import {
	ActionBarPrimitive,
	AssistantIf,
	ErrorPrimitive,
	MessagePrimitive,
	useAssistantState,
} from "@assistant-ui/react";
import { CheckIcon, CopyIcon, DownloadIcon, RefreshCwIcon } from "lucide-react";
import type { FC } from "react";
import { useContext } from "react";
import { BranchPicker } from "@/components/assistant-ui/branch-picker";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
	ThinkingStepsContext,
	ThinkingStepsDisplay,
} from "@/components/assistant-ui/thinking-steps";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

export const MessageError: FC = () => {
	return (
		<MessagePrimitive.Error>
			<ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
				<ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
			</ErrorPrimitive.Root>
		</MessagePrimitive.Error>
	);
};

/**
 * Custom component to render thinking steps from Context
 */
const ThinkingStepsPart: FC = () => {
	const thinkingStepsMap = useContext(ThinkingStepsContext);

	// Get the current message ID to look up thinking steps
	const messageId = useAssistantState(({ message }) => message?.id);
	const thinkingSteps = thinkingStepsMap.get(messageId) || [];

	// Check if this specific message is currently streaming
	// A message is streaming if: thread is running AND this is the last assistant message
	const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);
	const isLastMessage = useAssistantState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;

	if (thinkingSteps.length === 0) return null;

	return (
		<div className="mb-3">
			<ThinkingStepsDisplay steps={thinkingSteps} isThreadRunning={isMessageStreaming} />
		</div>
	);
};

const AssistantMessageInner: FC = () => {
	return (
		<>
			{/* Render thinking steps from message content - this ensures proper scroll tracking */}
			<ThinkingStepsPart />

			<div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
				<MessagePrimitive.Parts
					components={{
						Text: MarkdownText,
						tools: { Fallback: ToolFallback },
					}}
				/>
				<MessageError />
			</div>

			<div className="aui-assistant-message-footer mt-1 mb-5 ml-2 flex">
				<BranchPicker />
				<AssistantActionBar />
			</div>
		</>
	);
};

export const AssistantMessage: FC = () => {
	return (
		<MessagePrimitive.Root
			className="aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
			data-role="assistant"
		>
			<AssistantMessageInner />
		</MessagePrimitive.Root>
	);
};

const AssistantActionBar: FC = () => {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root -ml-1 col-start-3 row-start-2 flex gap-1 text-muted-foreground data-floating:absolute data-floating:rounded-md data-floating:border data-floating:bg-background data-floating:p-1 data-floating:shadow-sm"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy">
					<AssistantIf condition={({ message }) => message.isCopied}>
						<CheckIcon />
					</AssistantIf>
					<AssistantIf condition={({ message }) => !message.isCopied}>
						<CopyIcon />
					</AssistantIf>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			<ActionBarPrimitive.ExportMarkdown asChild>
				<TooltipIconButton tooltip="Export as Markdown">
					<DownloadIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.ExportMarkdown>
			<ActionBarPrimitive.Reload asChild>
				<TooltipIconButton tooltip="Refresh">
					<RefreshCwIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.Reload>
		</ActionBarPrimitive.Root>
	);
};
