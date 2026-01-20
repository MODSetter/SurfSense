import { ActionBarPrimitive, MessagePrimitive, useAssistantState } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { FileText, PencilIcon } from "lucide-react";
import { type FC, useState } from "react";
import { messageDocumentsMapAtom } from "@/atoms/chat/mentioned-documents.atom";
import { UserMessageAttachments } from "@/components/assistant-ui/attachment";
import { BranchPicker } from "@/components/assistant-ui/branch-picker";
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
			<img
				src={avatarUrl}
				alt={displayName || "User"}
				className="size-8 rounded-full object-cover"
				referrerPolicy="no-referrer"
				onError={() => setHasError(true)}
			/>
		);
	}

	return (
		<div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
			{initials}
		</div>
	);
};

export const UserMessage: FC = () => {
	const messageId = useAssistantState(({ message }) => message?.id);
	const messageDocumentsMap = useAtomValue(messageDocumentsMapAtom);
	const mentionedDocs = messageId ? messageDocumentsMap[messageId] : undefined;
	const metadata = useAssistantState(({ message }) => message?.metadata);
	const author = metadata?.custom?.author as AuthorMetadata | undefined;
	const hasAttachments = useAssistantState(
		({ message }) => message?.attachments && message.attachments.length > 0
	);

	return (
		<MessagePrimitive.Root
			className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 py-3 duration-150 [&:where(>*)]:col-start-2"
			data-role="user"
		>
			<div className="aui-user-message-content-wrapper col-start-2 min-w-0 flex items-end gap-2">
				<div className="flex-1 min-w-0">
					{/* Display attachments and mentioned documents */}
					{(hasAttachments || (mentionedDocs && mentionedDocs.length > 0)) && (
						<div className="flex flex-wrap items-end gap-2 mb-2 justify-end">
							{/* Attachments (images show as thumbnails, documents as chips) */}
							<UserMessageAttachments />
							{/* Mentioned documents as chips */}
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
					{/* Message bubble with action bar positioned relative to it */}
					<div className="relative">
						<div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
							<MessagePrimitive.Parts />
						</div>
						<div className="aui-user-action-bar-wrapper absolute top-1/2 right-full -translate-y-1/2 pr-1">
							<UserActionBar />
						</div>
					</div>
				</div>
				{/* User avatar - only shown in shared chats */}
				{author && (
					<div className="shrink-0 mb-1.5">
						<UserAvatar displayName={author.displayName} avatarUrl={author.avatarUrl} />
					</div>
				)}
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
