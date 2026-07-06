import {
	ActionBarPrimitive,
	AuiIf,
	MessagePrimitive,
	useAuiState,
	useMessagePartText,
} from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import {
	CheckIcon,
	CopyIcon,
	Folder as FolderIcon,
	MessageSquare,
	Pencil,
	Plug,
} from "lucide-react";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { type FC, useCallback, useState } from "react";
import { toast } from "sonner";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { messageDocumentsMapAtom } from "@/atoms/chat/mentioned-documents.atom";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { MentionChip } from "@/components/assistant-ui/mention-chip";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { parseMentionSegments } from "@/lib/chat/parse-mention-segments";

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
		<div className="flex size-8 items-center justify-center rounded-full bg-muted text-xs font-medium text-foreground select-none">
			{initials}
		</div>
	);
};

const UserTextPart: FC = () => {
	const messageId = useAuiState(({ message }) => message?.id);
	const part = useMessagePartText();
	const text = (part as { text?: string }).text ?? "";
	const messageDocumentsMap = useAtomValue(messageDocumentsMapAtom);
	const mentionedDocs = (messageId ? messageDocumentsMap[messageId] : undefined) ?? [];
	const openEditorPanel = useSetAtom(openEditorPanelAtom);
	const router = useRouter();
	const params = useParams();
	const searchSpaceIdParam = params?.workspace_id;
	const parsedSearchSpaceId = Array.isArray(searchSpaceIdParam)
		? Number(searchSpaceIdParam[0])
		: Number(searchSpaceIdParam);
	const resolvedSearchSpaceId = Number.isFinite(parsedSearchSpaceId)
		? parsedSearchSpaceId
		: undefined;

	const handleOpenDoc = useCallback(
		(docId: number, title: string) => {
			if (!resolvedSearchSpaceId) {
				toast.error("Cannot open document outside a search space.");
				return;
			}
			openEditorPanel({
				kind: "document",
				documentId: docId,
				searchSpaceId: resolvedSearchSpaceId,
				title,
			});
		},
		[openEditorPanel, resolvedSearchSpaceId]
	);

	const handleOpenThread = useCallback(
		(threadId: number) => {
			if (!resolvedSearchSpaceId) {
				toast.error("Cannot open chat outside a search space.");
				return;
			}
			router.push(`/dashboard/${resolvedSearchSpaceId}/new-chat/${threadId}`);
		},
		[resolvedSearchSpaceId, router]
	);

	const segments = parseMentionSegments(text, mentionedDocs);

	return (
		<p style={{ whiteSpace: "pre-line" }} className="wrap-break-word">
			{segments.map((segment) => {
				if (segment.type === "text") {
					return <span key={`txt-${segment.start}`}>{segment.value}</span>;
				}
				const isFolder = segment.doc.kind === "folder";
				const isConnector = segment.doc.kind === "connector";
				const isThread = segment.doc.kind === "thread";
				const icon = isFolder ? (
					<FolderIcon className="size-3.5" />
				) : isThread ? (
					<MessageSquare className="size-3.5" />
				) : isConnector ? (
					(getConnectorIcon(segment.doc.connector_type, "size-3.5") ?? (
						<Plug className="size-3.5" />
					))
				) : (
					getConnectorIcon(segment.doc.document_type ?? "UNKNOWN", "size-3.5")
				);
				return (
					<MentionChip
						key={`mention-${getMentionDocKey(segment.doc)}-${segment.start}`}
						icon={icon}
						label={segment.doc.title}
						tooltip={
							isFolder
								? `Folder: ${segment.doc.title}`
								: isThread
									? `Chat: ${segment.doc.title}`
									: isConnector
										? `Connector account: ${segment.doc.title}`
										: segment.doc.title
						}
						onClick={
							isThread
								? () => handleOpenThread(segment.doc.id)
								: isFolder || isConnector
									? undefined
									: () => handleOpenDoc(segment.doc.id, segment.doc.title)
						}
						className="mx-0.5"
					/>
				);
			})}
		</p>
	);
};

const userMessageParts = { Text: UserTextPart };

export const UserMessage: FC = () => {
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
						<div className="aui-user-message-content wrap-break-word rounded-xl bg-muted px-4 py-2.5 text-foreground">
							<MessagePrimitive.Parts components={userMessageParts} />
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
