import { ActionBarPrimitive, AuiIf, MessagePrimitive, useAuiState } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { CheckIcon, CopyIcon, Pencil } from "lucide-react";
import Image from "next/image";
import { type FC, useState } from "react";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { messageDocumentsMapAtom } from "@/atoms/chat/mentioned-documents.atom";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

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
	const messageText = useAuiState(({ message }) =>
		(message?.content ?? [])
			.map((part) =>
				typeof part === "object" &&
				part !== null &&
				"type" in part &&
				(part as { type?: string }).type === "text" &&
				"text" in part
					? String((part as { text?: string }).text ?? "")
					: ""
			)
			.join("")
	);
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
						<div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
							{mentionedDocs && mentionedDocs.length > 0 ? (
								<UserMessageWithMentionChips text={messageText} mentionedDocs={mentionedDocs} />
							) : (
								<MessagePrimitive.Parts />
							)}
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

const UserMessageWithMentionChips: FC<{
	text: string;
	mentionedDocs: { id: number; title: string; document_type: string }[];
}> = ({ text, mentionedDocs }) => {
	type Segment =
		| { type: "text"; value: string; start: number }
		| { type: "mention"; doc: { id: number; title: string; document_type: string }; start: number };

	const tokens = mentionedDocs
		.map((doc) => ({ doc, token: `@${doc.title}` }))
		.sort((a, b) => b.token.length - a.token.length);

	const segments: Segment[] = [];
	let i = 0;
	let buffer = "";
	let bufferStart = 0;
	while (i < text.length) {
		const tokenMatch = tokens.find(({ token }) => text.startsWith(token, i));
		if (tokenMatch) {
			if (buffer) {
				segments.push({ type: "text", value: buffer, start: bufferStart });
				buffer = "";
			}
			segments.push({ type: "mention", doc: tokenMatch.doc, start: i });
			i += tokenMatch.token.length;
			bufferStart = i;
			continue;
		}
		if (!buffer) bufferStart = i;
		buffer += text[i];
		i += 1;
	}
	if (buffer) {
		segments.push({ type: "text", value: buffer, start: bufferStart });
	}

	return (
		<span className="whitespace-pre-wrap break-words">
			{segments.map((segment) =>
				segment.type === "text" ? (
					<span key={`txt-${segment.start}`}>{segment.value}</span>
				) : (
					<span
						key={`mention-${segment.doc.document_type}:${segment.doc.id}-${segment.start}`}
						className="inline-flex items-center gap-1 mx-0.5 px-1 py-0.5 rounded bg-primary/10 text-xs font-bold text-primary/60 select-none align-baseline"
						title={segment.doc.title}
					>
						<span className="flex items-center text-muted-foreground">
							{getConnectorIcon(segment.doc.document_type ?? "UNKNOWN", "h-3 w-3")}
						</span>
						<span className="max-w-[120px] truncate">{segment.doc.title}</span>
					</span>
				)
			)}
		</span>
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
