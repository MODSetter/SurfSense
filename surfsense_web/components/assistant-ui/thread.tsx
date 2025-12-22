import {
	ActionBarPrimitive,
	AssistantIf,
	BranchPickerPrimitive,
	ComposerPrimitive,
	ErrorPrimitive,
	MessagePrimitive,
	ThreadPrimitive,
	useAssistantState,
	useMessage,
} from "@assistant-ui/react";
import {
	ArrowDownIcon,
	ArrowUpIcon,
	Brain,
	CheckCircle2,
	CheckIcon,
	ChevronLeftIcon,
	ChevronRightIcon,
	CopyIcon,
	DownloadIcon,
	Loader2,
	PencilIcon,
	RefreshCwIcon,
	Search,
	Sparkles,
	SquareIcon,
} from "lucide-react";
import Image from "next/image";
import type { FC } from "react";
import { useAtomValue } from "jotai";
import {
	ComposerAddAttachment,
	ComposerAttachments,
	UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import {
	ChainOfThought,
	ChainOfThoughtContent,
	ChainOfThoughtItem,
	ChainOfThoughtStep,
	ChainOfThoughtTrigger,
} from "@/components/prompt-kit/chain-of-thought";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";

/**
 * Props for the Thread component
 */
interface ThreadProps {
	messageThinkingSteps?: Map<string, ThinkingStep[]>;
}

// Context to pass thinking steps to AssistantMessage
import { createContext, useContext } from "react";

const ThinkingStepsContext = createContext<Map<string, ThinkingStep[]>>(new Map());

/**
 * Get icon based on step status and title
 */
function getStepIcon(status: "pending" | "in_progress" | "completed", title: string) {
	const titleLower = title.toLowerCase();
	
	if (status === "in_progress") {
		return <Loader2 className="size-4 animate-spin text-primary" />;
	}
	
	if (status === "completed") {
		return <CheckCircle2 className="size-4 text-emerald-500" />;
	}
	
	if (titleLower.includes("search") || titleLower.includes("knowledge")) {
		return <Search className="size-4 text-muted-foreground" />;
	}
	
	if (titleLower.includes("analy") || titleLower.includes("understand")) {
		return <Brain className="size-4 text-muted-foreground" />;
	}
	
	return <Sparkles className="size-4 text-muted-foreground" />;
}

/**
 * Chain of thought display component
 */
const ThinkingStepsDisplay: FC<{ steps: ThinkingStep[] }> = ({ steps }) => {
	if (steps.length === 0) return null;
	
	return (
		<div className="mx-auto w-full max-w-(--thread-max-width) px-2 py-2">
			<ChainOfThought>
				{steps.map((step) => {
					const icon = getStepIcon(step.status, step.title);
					return (
						<ChainOfThoughtStep 
							key={step.id} 
							defaultOpen={step.status === "in_progress"}
						>
							<ChainOfThoughtTrigger
								leftIcon={icon}
								swapIconOnHover={step.status !== "in_progress"}
								className={cn(
									step.status === "in_progress" && "text-foreground font-medium",
									step.status === "completed" && "text-muted-foreground"
								)}
							>
								{step.title}
							</ChainOfThoughtTrigger>
							{step.items && step.items.length > 0 && (
								<ChainOfThoughtContent>
									{step.items.map((item, index) => (
										<ChainOfThoughtItem key={`${step.id}-item-${index}`}>
											{item}
										</ChainOfThoughtItem>
									))}
								</ChainOfThoughtContent>
							)}
						</ChainOfThoughtStep>
					);
				})}
			</ChainOfThought>
		</div>
	);
};

export const Thread: FC<ThreadProps> = ({ messageThinkingSteps = new Map() }) => {
	return (
		<ThinkingStepsContext.Provider value={messageThinkingSteps}>
			<ThreadPrimitive.Root
				className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
				style={{
					["--thread-max-width" as string]: "44rem",
				}}
			>
				<ThreadPrimitive.Viewport
					turnAnchor="top"
					className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll scroll-smooth px-4 pt-4"
				>
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

const ThreadScrollToBottom: FC = () => {
	return (
		<ThreadPrimitive.ScrollToBottom asChild>
			<TooltipIconButton
				tooltip="Scroll to bottom"
				variant="outline"
				className="aui-thread-scroll-to-bottom -top-12 absolute z-10 self-center rounded-full p-4 disabled:invisible dark:bg-background dark:hover:bg-accent"
			>
				<ArrowDownIcon />
			</TooltipIconButton>
		</ThreadPrimitive.ScrollToBottom>
	);
};

const getTimeBasedGreeting = (userEmail?: string): string => {
	const hour = new Date().getHours();
	
	// Extract first name from email if available
	const firstName = userEmail
		? userEmail.split("@")[0].split(".")[0].charAt(0).toUpperCase() + 
		  userEmail.split("@")[0].split(".")[0].slice(1)
		: null;
	
	// Array of greeting variations for each time period
	const morningGreetings = [
		"Good morning",
		"Rise and shine",
		"Morning",
		"Hey there",
		"Welcome back",
	];
	
	const afternoonGreetings = [
		"Good afternoon",
		"Afternoon",
		"Hey there",
		"Welcome back",
		"Hope you're having a great day",
	];
	
	const eveningGreetings = [
		"Good evening",
		"Evening",
		"Hey there",
		"Welcome back",
		"Hope you had a great day",
	];
	
	const nightGreetings = [
		"Late night",
		"Still up",
		"Hey there",
		"Welcome back",
		"Burning the midnight oil",
	];
	
	// Select a random greeting based on time
	let greeting: string;
	if (hour < 12) {
		greeting = morningGreetings[Math.floor(Math.random() * morningGreetings.length)];
	} else if (hour < 17) {
		greeting = afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)];
	} else if (hour < 21) {
		greeting = eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)];
	} else {
		greeting = nightGreetings[Math.floor(Math.random() * nightGreetings.length)];
	}
	
	// Add personalization with first name if available
	if (firstName) {
		return `${greeting}, ${firstName}!`;
	}
	
	return `${greeting}!`;
};

const ThreadWelcome: FC = () => {
	const { data: user } = useAtomValue(currentUserAtom);
	
	return (
		<div className="aui-thread-welcome-root mx-auto flex w-full max-w-(--thread-max-width) grow flex-col items-center px-4 relative">
			{/* Greeting positioned near the composer */}
			<div className="aui-thread-welcome-message absolute top-1/2 left-0 right-0 flex flex-col items-center text-center z-10 -translate-y-[calc(50%+100px)]">
				<h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-2 animate-in text-4xl delay-100 duration-500 ease-out fill-mode-both flex items-center gap-3">
					{/** biome-ignore lint/a11y/noStaticElementInteractions: wrong lint error, this is a workaround to fix the lint error */}
					<div
						className="relative cursor-pointer"
						onMouseMove={(e) => {
							const rect = e.currentTarget.getBoundingClientRect();
							const x = (e.clientX - rect.left - rect.width / 2) / 3;
							const y = (e.clientY - rect.top - rect.height / 2) / 3;
							e.currentTarget.style.setProperty("--mag-x", `${x}px`);
							e.currentTarget.style.setProperty("--mag-y", `${y}px`);
						}}
						onMouseLeave={(e) => {
							e.currentTarget.style.setProperty("--mag-x", "0px");
							e.currentTarget.style.setProperty("--mag-y", "0px");
						}}
					>
						<Image
							src="/icon-128.png"
							alt="SurfSense"
							width={32}
							height={32}
							className="rounded-full transition-transform duration-200 ease-out"
							style={{
								transform: "translate(var(--mag-x, 0), var(--mag-y, 0))",
							}}
						/>
					</div>
					{getTimeBasedGreeting(user?.email)}
				</h1>
			</div>
			{/* Composer centered in the middle of the screen */}
			<div className="fade-in slide-in-from-bottom-3 animate-in delay-200 duration-500 ease-out fill-mode-both w-full flex items-center justify-center absolute top-1/2 left-0 right-0 -translate-y-1/2">
				<Composer />
			</div>
		</div>
	);
};

const Composer: FC = () => {
	return (
		<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
			<ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone flex w-full flex-col rounded-2xl border-input bg-muted px-1 pt-2 outline-none transition-shadow data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-accent/50">
				<ComposerAttachments />
				<ComposerPrimitive.Input
					placeholder="Ask SurfSense"
					className="aui-composer-input mb-1 max-h-32 min-h-14 w-full resize-none bg-transparent px-4 pt-2 pb-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-0"
					rows={1}
					autoFocus
					aria-label="Message input"
				/>
				<ComposerAction />
			</ComposerPrimitive.AttachmentDropzone>
		</ComposerPrimitive.Root>
	);
};

const ComposerAction: FC = () => {
	// Check if any attachments are still being processed (running AND progress < 100)
	// When progress is 100, processing is done but waiting for send()
	const hasProcessingAttachments = useAssistantState(({ composer }) =>
		composer.attachments?.some((att) => {
			const status = att.status;
			if (status?.type !== "running") return false;
			const progress = (status as { type: "running"; progress?: number }).progress;
			return progress === undefined || progress < 100;
		})
	);

	// Check if composer text is empty
	const isComposerEmpty = useAssistantState(({ composer }) => {
		const text = composer.text?.trim() || "";
		return text.length === 0;
	});

	const isSendDisabled = hasProcessingAttachments || isComposerEmpty;

	return (
		<div className="aui-composer-action-wrapper relative mx-2 mb-2 flex items-center justify-between">
			<ComposerAddAttachment />

			{/* Show processing indicator when attachments are being processed */}
			{hasProcessingAttachments && (
				<div className="flex items-center gap-1.5 text-muted-foreground text-xs">
					<Loader2 className="size-3 animate-spin" />
					<span>Processing...</span>
				</div>
			)}

			<AssistantIf condition={({ thread }) => !thread.isRunning}>
				<ComposerPrimitive.Send asChild disabled={isSendDisabled}>
					<TooltipIconButton
						tooltip={
							hasProcessingAttachments
								? "Wait for attachments to process"
								: isComposerEmpty
									? "Enter a message to send"
									: "Send message"
						}
						side="bottom"
						type="submit"
						variant="default"
						size="icon"
						className={cn(
							"aui-composer-send size-8 rounded-full",
							isSendDisabled && "cursor-not-allowed opacity-50"
						)}
						aria-label="Send message"
						disabled={isSendDisabled}
					>
						<ArrowUpIcon className="aui-composer-send-icon size-4" />
					</TooltipIconButton>
				</ComposerPrimitive.Send>
			</AssistantIf>

			<AssistantIf condition={({ thread }) => thread.isRunning}>
				<ComposerPrimitive.Cancel asChild>
					<Button
						type="button"
						variant="default"
						size="icon"
						className="aui-composer-cancel size-8 rounded-full"
						aria-label="Stop generating"
					>
						<SquareIcon className="aui-composer-cancel-icon size-3 fill-current" />
					</Button>
				</ComposerPrimitive.Cancel>
			</AssistantIf>
		</div>
	);
};

const MessageError: FC = () => {
	return (
		<MessagePrimitive.Error>
			<ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
				<ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
			</ErrorPrimitive.Root>
		</MessagePrimitive.Error>
	);
};

const AssistantMessageInner: FC = () => {
	const thinkingStepsMap = useContext(ThinkingStepsContext);
	
	// Get the current message ID to look up thinking steps
	const messageId = useMessage((m) => m.id);
	const thinkingSteps = thinkingStepsMap.get(messageId) || [];
	
	return (
		<>
			{/* Show thinking steps BEFORE the text response */}
			{thinkingSteps.length > 0 && (
				<div className="mb-3">
					<ThinkingStepsDisplay steps={thinkingSteps} />
				</div>
			)}
			
			<div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
				<MessagePrimitive.Parts
					components={{
						Text: MarkdownText,
						tools: { Fallback: ToolFallback },
					}}
				/>
				<MessageError />
			</div>

			<div className="aui-assistant-message-footer mt-1 ml-2 flex">
				<BranchPicker />
				<AssistantActionBar />
			</div>
		</>
	);
};

const AssistantMessage: FC = () => {
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

const UserMessage: FC = () => {
	return (
		<MessagePrimitive.Root
			className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 py-3 duration-150 [&:where(>*)]:col-start-2"
			data-role="user"
		>
			<UserMessageAttachments />

			<div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
				<div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
					<MessagePrimitive.Parts />
				</div>
				<div className="aui-user-action-bar-wrapper -translate-x-full -translate-y-1/2 absolute top-1/2 left-0 pr-2">
					<UserActionBar />
				</div>
			</div>

			<BranchPicker className="aui-user-branch-picker -mr-1 col-span-full col-start-1 row-start-3 justify-end" />
		</MessagePrimitive.Root>
	);
};

const UserActionBar: FC = () => {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			className="aui-user-action-bar-root flex flex-col items-end"
		>
			<ActionBarPrimitive.Edit asChild>
				<TooltipIconButton tooltip="Edit" className="aui-user-action-edit p-4">
					<PencilIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.Edit>
		</ActionBarPrimitive.Root>
	);
};

const EditComposer: FC = () => {
	return (
		<MessagePrimitive.Root className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col px-2 py-3">
			<ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-[85%] flex-col rounded-2xl bg-muted">
				<ComposerPrimitive.Input
					className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent p-4 text-foreground text-sm outline-none"
					autoFocus
				/>
				<div className="aui-edit-composer-footer mx-3 mb-3 flex items-center gap-2 self-end">
					<ComposerPrimitive.Cancel asChild>
						<Button variant="ghost" size="sm">
							Cancel
						</Button>
					</ComposerPrimitive.Cancel>
					<ComposerPrimitive.Send asChild>
						<Button size="sm">Update</Button>
					</ComposerPrimitive.Send>
				</div>
			</ComposerPrimitive.Root>
		</MessagePrimitive.Root>
	);
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({ className, ...rest }) => {
	return (
		<BranchPickerPrimitive.Root
			hideWhenSingleBranch
			className={cn(
				"aui-branch-picker-root -ml-2 mr-2 inline-flex items-center text-muted-foreground text-xs",
				className
			)}
			{...rest}
		>
			<BranchPickerPrimitive.Previous asChild>
				<TooltipIconButton tooltip="Previous">
					<ChevronLeftIcon />
				</TooltipIconButton>
			</BranchPickerPrimitive.Previous>
			<span className="aui-branch-picker-state font-medium">
				<BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
			</span>
			<BranchPickerPrimitive.Next asChild>
				<TooltipIconButton tooltip="Next">
					<ChevronRightIcon />
				</TooltipIconButton>
			</BranchPickerPrimitive.Next>
		</BranchPickerPrimitive.Root>
	);
};
