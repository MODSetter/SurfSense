import {
	ActionBarPrimitive,
	AssistantIf,
	BranchPickerPrimitive,
	ComposerPrimitive,
	ErrorPrimitive,
	MessagePrimitive,
	ThreadPrimitive,
} from "@assistant-ui/react";
import { useAtom, useAtomValue } from "jotai";
import {
	ArrowDownIcon,
	ArrowUpIcon,
	CheckIcon,
	ChevronLeftIcon,
	ChevronRightIcon,
	CopyIcon,
	DownloadIcon,
	PencilIcon,
	RefreshCwIcon,
	SquareIcon,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { type FC, useEffect, useMemo, useRef } from "react";
import { activeChatAtom } from "@/atoms/chats/chat-query.atoms";
import { activeChatIdAtom } from "@/atoms/chats/ui.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import {
	ComposerAddAttachment,
	ComposerAttachments,
	UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Button } from "@/components/ui/button";
import { useSearchSourceConnectors } from "@/hooks";
import { useChatState } from "@/hooks/use-chat";
import { cn } from "@/lib/utils";
import { AnimatedEmptyState } from "../chat/AnimatedEmptyState";
import { ConnectorGroup } from "../chat/ConnectorGroup";
import { useState } from "react";
import { DocumentsDataTable } from "@/components/chat/DocumentsDataTable";
import { Document } from "@/contracts/types/document.types";

export const Thread: FC = () => {
	return (
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
					<ThreadLogo />
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
					<Composer onDocumentsMention={(documents) => {
						console.log(documents);
					}} />
				</ThreadPrimitive.ViewportFooter>
			</ThreadPrimitive.Viewport>
		</ThreadPrimitive.Root>
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

const ThreadLogo: FC = () => {
	return <AnimatedEmptyState />;
};

const Composer: FC<{onDocumentsMention?: (documents: Document[]) => void}> = ({onDocumentsMention}) => {
	const [showDocumentPopover, setShowDocumentPopover] = useState(false);
	const inputRef = useRef<HTMLTextAreaElement | null>(null);
	const { search_space_id } = useParams();

	const handleInputOrKeyUp = (
		e: React.FormEvent<HTMLTextAreaElement> | React.KeyboardEvent<HTMLTextAreaElement>
	) => {
		const textarea = e.currentTarget;
		const value = textarea.value;
		const selectionStart = textarea.selectionStart;
		// Only open if the last character before the caret is exactly '@'
		if (
			selectionStart !== null &&
			value[selectionStart - 1] === "@" &&
			value.length === selectionStart
		) {
			setShowDocumentPopover(true);
		} else {
			setShowDocumentPopover(false);
		}
	};

	const handleDocumentsMention = (documents: Document[]) => {
		onDocumentsMention?.(documents);
	};

	return (
		<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
			<ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone flex w-full flex-col rounded-2xl border border-input bg-background px-1 pt-2 outline-none transition-shadow has-[textarea:focus-visible]:border-ring has-[textarea:focus-visible]:ring-2 has-[textarea:focus-visible]:ring-ring/20 data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-accent/50">
				<ComposerAttachments />
				<ComposerPrimitive.Input
					ref={inputRef}
					onInput={handleInputOrKeyUp}
					onKeyUp={handleInputOrKeyUp}
					placeholder="Send a message..."
					className="aui-composer-input mb-1 max-h-32 min-h-14 w-full resize-none bg-transparent px-4 pt-2 pb-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-0"
					rows={1}
					autoFocus
					aria-label="Message input"
				/>
				{showDocumentPopover && (
					<div
						style={{ position: "absolute", bottom: "8rem", left: 0, zIndex: 50 }}
						className="shadow-lg rounded-md border bg-popover"
					>
						<div className="p-2 max-h-96 w-full overflow-auto">
							<DocumentsDataTable
								searchSpaceId={Number(search_space_id)}
								onSelectionChange={handleDocumentsMention}
								onDone={() => setShowDocumentPopover(false)}
								initialSelectedDocuments={[]}
								viewOnly={true}
							/>
						</div>
					</div>
				)}

				<ComposerAction />
			</ComposerPrimitive.AttachmentDropzone>
		</ComposerPrimitive.Root>
	);
};

const ComposerAction: FC = () => {
	const { search_space_id } = useParams();
	const hasSetInitialConnectors = useRef(false);
	const activeChatId = useAtomValue(activeChatIdAtom);
	const isNewChat = !activeChatId;
	const { data: activeChatState, isFetching: isChatLoading } = useAtomValue(activeChatAtom);

	// Reset the flag when chat ID changes (but not hasInitiatedResponse - we need to remember if we already initiated)
	useEffect(() => {
		hasSetInitialConnectors.current = false;
	}, [activeChatId]);

	const { token, selectedConnectors, setSelectedConnectors, selectedDocuments } = useChatState({
		search_space_id: search_space_id as string,
		chat_id: activeChatId ?? undefined,
	});

	// Fetch all available sources (document types + live search connectors)
	// Use the documentTypeCountsAtom for fetching document types
	const [documentTypeCountsQuery] = useAtom(documentTypeCountsAtom);
	const { data: documentTypeCountsData } = documentTypeCountsQuery;

	// Transform the response into the expected format
	const documentTypes = useMemo(() => {
		if (!documentTypeCountsData) return [];
		return Object.entries(documentTypeCountsData).map(([type, count]) => ({
			type,
			count,
		}));
	}, [documentTypeCountsData]);

	const { connectors: searchConnectors } = useSearchSourceConnectors(
		false,
		Number(search_space_id)
	);

	// Filter for non-indexable connectors (live search)
	const liveSearchConnectors = useMemo(
		() => searchConnectors.filter((connector) => !connector.is_indexable),
		[searchConnectors]
	);

	// Memoize document IDs to prevent infinite re-renders
	const documentIds = useMemo(() => {
		return selectedDocuments.map((doc) => doc.id);
	}, [selectedDocuments]);

	// Memoize connector types to prevent infinite re-renders
	const connectorTypes = useMemo(() => {
		return selectedConnectors;
	}, [selectedConnectors]);

	useEffect(() => {
		if (token && !isNewChat && activeChatId) {
			const chatData = activeChatState?.chatDetails;
			if (!chatData) return;

			// Update configuration from chat data
			// researchMode is always "QNA", no need to set from chat data

			if (chatData.initial_connectors && Array.isArray(chatData.initial_connectors)) {
				setSelectedConnectors(chatData.initial_connectors);
			}
		}
	}, [token, isNewChat, activeChatId, isChatLoading]);

	// Set all sources as default for new chats (only once on initial mount)
	useEffect(() => {
		if (
			isNewChat &&
			!hasSetInitialConnectors.current &&
			selectedConnectors.length === 0 &&
			documentTypes.length > 0
		) {
			// Combine all document types and live search connectors
			const allSourceTypes = [
				...documentTypes.map((dt) => dt.type),
				...liveSearchConnectors.map((c) => c.connector_type),
			];

			if (allSourceTypes.length > 0) {
				setSelectedConnectors(allSourceTypes);
				hasSetInitialConnectors.current = true;
			}
		}
	}, [
		isNewChat,
		documentTypes,
		liveSearchConnectors,
		selectedConnectors.length,
		setSelectedConnectors,
	]);

	return (
		<div className="aui-composer-action-wrapper relative mx-2 mb-2 flex items-center justify-between">
			<ComposerAddAttachment />
			<div className="flex flex-row gap-2 w-full">
				<ConnectorGroup
					connectors={selectedConnectors.map((connector) => ({
						id: connector,
						name: connector,
						type: connector,
					}))}
				/>
			</div>
			<AssistantIf condition={({ thread }) => !thread.isRunning}>
				<ComposerPrimitive.Send asChild>
					<TooltipIconButton
						tooltip="Send message"
						side="bottom"
						type="submit"
						variant="default"
						size="icon"
						className="aui-composer-send size-8 rounded-full"
						aria-label="Send message"
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

const AssistantMessage: FC = () => {
	return (
		<MessagePrimitive.Root
			className="aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
			data-role="assistant"
		>
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
