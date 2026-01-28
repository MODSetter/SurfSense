"use client";

import {
	ActionBarPrimitive,
	AssistantIf,
	MessagePrimitive,
	ThreadPrimitive,
	useAssistantState,
} from "@assistant-ui/react";
import { CheckIcon, CopyIcon } from "lucide-react";
import { type FC, type ReactNode, useState } from "react";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

interface PublicThreadProps {
	footer?: ReactNode;
}

/**
 * Read-only thread component for public chat viewing.
 * No composer, no edit capabilities - just message display.
 */
export const PublicThread: FC<PublicThreadProps> = ({ footer }) => {
	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-background"
			style={{
				["--thread-max-width" as string]: "44rem",
			}}
		>
			<ThreadPrimitive.Viewport className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 pt-4">
				<ThreadPrimitive.Messages
					components={{
						UserMessage: PublicUserMessage,
						AssistantMessage: PublicAssistantMessage,
					}}
				/>

				{/* Spacer to ensure footer doesn't overlap last message */}
				<div className="h-24" />
			</ThreadPrimitive.Viewport>

			{footer && (
				<div className="sticky bottom-0 z-20 border-t bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60">
					{footer}
				</div>
			)}
		</ThreadPrimitive.Root>
	);
};

/**
 * User avatar component with fallback to initials
 */
interface AuthorMetadata {
	displayName: string | null;
	avatarUrl: string | null;
}

const UserAvatar: FC<AuthorMetadata & { hasError: boolean; onError: () => void }> = ({
	displayName,
	avatarUrl,
	hasError,
	onError,
}) => {
	const initials = displayName
		? displayName
				.split(" ")
				.map((n) => n[0])
				.join("")
				.toUpperCase()
				.slice(0, 2)
		: "U";

	if (avatarUrl && !hasError) {
		return (
			<img
				src={avatarUrl}
				alt={displayName || "User"}
				className="size-8 rounded-full object-cover"
				referrerPolicy="no-referrer"
				onError={onError}
			/>
		);
	}

	return (
		<div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
			{initials}
		</div>
	);
};

const PublicUserMessage: FC = () => {
	const metadata = useAssistantState(({ message }) => message?.metadata);
	const author = metadata?.custom?.author as AuthorMetadata | undefined;

	return (
		<MessagePrimitive.Root
			className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 py-3 duration-150 [&:where(>*)]:col-start-2"
			data-role="user"
		>
			<div className="aui-user-message-content-wrapper col-start-2 min-w-0 flex items-end gap-2">
				<div className="flex-1 min-w-0">
					<div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
						<MessagePrimitive.Parts />
					</div>
				</div>
				{author && (
					<div className="shrink-0 mb-1.5">
						<UserAvatarWithState displayName={author.displayName} avatarUrl={author.avatarUrl} />
					</div>
				)}
			</div>
		</MessagePrimitive.Root>
	);
};

const UserAvatarWithState: FC<AuthorMetadata> = ({ displayName, avatarUrl }) => {
	const [hasError, setHasError] = useState(false);
	return (
		<UserAvatar
			displayName={displayName}
			avatarUrl={avatarUrl}
			hasError={hasError}
			onError={() => setHasError(true)}
		/>
	);
};

const PublicAssistantMessage: FC = () => {
	return (
		<MessagePrimitive.Root
			className="aui-assistant-message-root group fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
			data-role="assistant"
		>
			<div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
				<MessagePrimitive.Parts
					components={{
						Text: MarkdownText,
						tools: { Fallback: ToolFallback },
					}}
				/>
			</div>

			<div className="aui-assistant-message-footer mt-1 mb-5 ml-2 flex">
				<PublicAssistantActionBar />
			</div>
		</MessagePrimitive.Root>
	);
};

const PublicAssistantActionBar: FC = () => {
	return (
		<ActionBarPrimitive.Root
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root -ml-1 flex gap-1 text-muted-foreground data-floating:absolute data-floating:rounded-md data-floating:border data-floating:bg-background data-floating:p-1 data-floating:shadow-sm"
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
		</ActionBarPrimitive.Root>
	);
};
