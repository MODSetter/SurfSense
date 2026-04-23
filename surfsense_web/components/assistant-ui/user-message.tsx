import { ActionBarPrimitive, AuiIf, MessagePrimitive, useAuiState } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { CheckIcon, CopyIcon, FileText, Pencil } from "lucide-react";
import Image from "next/image";
import { type FC, useState } from "react";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { messageDocumentsMapAtom } from "@/atoms/chat/mentioned-documents.atom";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

interface AuthorMetadata {
	displayName: string | null;
	avatarUrl: string | null;
}

const UserAvatar: FC<AuthorMetadata> = ({ displayName, avatarUrl }) => {
	const [hasError, setHasError] = useState(false);

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
			<Image
				src={avatarUrl}
				alt={displayName || "User"}
				width={32}
				height={32}
				className="size-8 rounded-full object-cover"
				referrerPolicy="no-referrer"
				onError={() => setHasError(true)}
				unoptimized
			/>
		);
	}

	return (
		<div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary select-none">
			{initials}
		</div>
	);
};

export const UserMessage: FC = () => {
	const messageId = useAuiState(({ message }) => message?.id);
	const messageDocumentsMap = useAtomValue(messageDocumentsMapAtom);
	const mentionedDocs = messageId ? messageDocumentsMap[messageId] : undefined;
	const metadata = useAuiState(({ message }) => message?.metadata);
	const author = metadata?.custom?.author as AuthorMetadata | undefined;
	const isSharedChat = useAtomValue(currentThreadAtom).visibility === "SEARCH_SPACE";
	const showAvatar = isSharedChat && !!author;

	return (
		<MessagePrimitive.Root
			className="group/user-msg aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 pt-3 pb-8 duration-150 [&:where(>*)]:col-start-2"
			data-role="user"
		>
			<div className="col-start-2 min-w-0">
				<div className="aui-user-message-content-wrapper flex items-end gap-2">
					<div className="relative flex-1 min-w-0">
						{mentionedDocs && mentionedDocs.length > 0 && (
							<div className="flex flex-wrap items-end gap-2 mb-2 justify-end">
								{mentionedDocs?.map((doc) => (
									<span
										key={`${doc.document_type}:${doc.id}`}
										className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-xs font-medium text-primary border border-primary/20"
										title={doc.title}
									>
										<FileText className="size-3" />
										<span className="max-w-[150px] truncate">{doc.title}</span>
									</span>
								))}
							</div>
						)}
						<div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
							<MessagePrimitive.Parts />
						</div>
						<div className="absolute right-0 top-full mt-1 z-10 opacity-100 pointer-events-auto md:opacity-0 md:pointer-events-none md:transition-opacity md:duration-200 md:delay-300 md:group-hover/user-msg:opacity-100 md:group-hover/user-msg:delay-0 md:group-hover/user-msg:pointer-events-auto">
							<UserActionBar />
						</div>
					</div>
					{showAvatar && (
						<div className="shrink-0 mb-1.5">
							<UserAvatar displayName={author.displayName} avatarUrl={author.avatarUrl} />
						</div>
					)}
				</div>
			</div>
		</MessagePrimitive.Root>
	);
};

const UserActionBar: FC = () => {
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);

	// Get current message ID
	const currentMessageId = useAuiState(({ message }) => message?.id);

	// Find the last user message ID in the thread (computed once, memoized by selector)
	const lastUserMessageId = useAuiState(({ thread }) => {
		const messages = thread.messages;
		for (let i = messages.length - 1; i >= 0; i--) {
			if (messages[i].role === "user") {
				return messages[i].id;
			}
		}
		return null;
	});

	// Simple comparison - no iteration needed per message
	const isLastUserMessage = currentMessageId === lastUserMessageId;

	// Show edit button only on the last user message and when thread is not running
	const canEdit = isLastUserMessage && !isThreadRunning;

	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			className="aui-user-action-bar-root flex items-center justify-end gap-1 text-muted-foreground"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy">
					<AuiIf condition={({ message }) => message.isCopied}>
						<CheckIcon />
					</AuiIf>
					<AuiIf condition={({ message }) => !message.isCopied}>
						<CopyIcon />
					</AuiIf>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			{canEdit && (
				<ActionBarPrimitive.Edit asChild>
					<TooltipIconButton tooltip="Edit" className="aui-user-action-edit">
						<Pencil />
					</TooltipIconButton>
				</ActionBarPrimitive.Edit>
			)}
		</ActionBarPrimitive.Root>
	);
};
