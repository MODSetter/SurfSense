"use client";

import {
	AttachmentPrimitive,
	ComposerPrimitive,
	MessagePrimitive,
	useAssistantApi,
	useAssistantState,
} from "@assistant-ui/react";
import { FileText, Paperclip, PlusIcon, Upload, XIcon } from "lucide-react";
import Image from "next/image";
import { type FC, type PropsWithChildren, useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/shallow";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useDocumentUploadDialog } from "./document-upload-popup";

const useFileSrc = (file: File | undefined) => {
	const [src, setSrc] = useState<string | undefined>(undefined);

	useEffect(() => {
		if (!file) {
			setSrc(undefined);
			return;
		}

		const objectUrl = URL.createObjectURL(file);
		setSrc(objectUrl);

		return () => {
			URL.revokeObjectURL(objectUrl);
		};
	}, [file]);

	return src;
};

const useAttachmentSrc = () => {
	const { file, src } = useAssistantState(
		useShallow(({ attachment }): { file?: File; src?: string } => {
			if (!attachment || attachment.type !== "image") return {};

			// First priority: use File object if available (for new uploads)
			if (attachment.file) return { file: attachment.file };

			// Second priority: use stored imageDataUrl (for persisted messages)
			// This is stored in our custom ChatAttachment interface
			const customAttachment = attachment as { imageDataUrl?: string };
			if (customAttachment.imageDataUrl) {
				return { src: customAttachment.imageDataUrl };
			}

			// Third priority: try to extract from content array (standard assistant-ui format)
			if (Array.isArray(attachment.content)) {
				const contentSrc = attachment.content.filter((c) => c.type === "image")[0]?.image;
				if (contentSrc) return { src: contentSrc };
			}

			return {};
		})
	);

	return useFileSrc(file) ?? src;
};

type AttachmentPreviewProps = {
	src: string;
};

const AttachmentPreview: FC<AttachmentPreviewProps> = ({ src }) => {
	const [isLoaded, setIsLoaded] = useState(false);
	return (
		<Image
			src={src}
			alt="Image Preview"
			width={1}
			height={1}
			className={
				isLoaded
					? "aui-attachment-preview-image-loaded block h-auto max-h-[80vh] w-auto max-w-full object-contain"
					: "aui-attachment-preview-image-loading hidden"
			}
			onLoadingComplete={() => setIsLoaded(true)}
			priority={false}
		/>
	);
};

const AttachmentPreviewDialog: FC<PropsWithChildren> = ({ children }) => {
	const src = useAttachmentSrc();

	if (!src) return children;

	return (
		<Dialog>
			<DialogTrigger
				className="aui-attachment-preview-trigger cursor-pointer transition-colors hover:bg-accent/50"
				asChild
			>
				{children}
			</DialogTrigger>
			<DialogContent className="aui-attachment-preview-dialog-content p-2 sm:max-w-3xl [&>button]:rounded-full [&>button]:bg-foreground/60 [&>button]:p-1 [&>button]:opacity-100 [&>button]:ring-0! [&_svg]:text-background [&>button]:hover:[&_svg]:text-destructive">
				<DialogTitle className="aui-sr-only sr-only">Image Attachment Preview</DialogTitle>
				<div className="aui-attachment-preview relative mx-auto flex max-h-[80dvh] w-full items-center justify-center overflow-hidden bg-background">
					<AttachmentPreview src={src} />
				</div>
			</DialogContent>
		</Dialog>
	);
};

const AttachmentThumb: FC = () => {
	const isImage = useAssistantState(({ attachment }) => attachment?.type === "image");
	// Check if actively processing (running AND progress < 100)
	// When progress is 100, processing is done but waiting for send()
	const isProcessing = useAssistantState(({ attachment }) => {
		const status = attachment?.status;
		if (status?.type !== "running") return false;
		// If progress is defined and equals 100, processing is complete
		const progress = (status as { type: "running"; progress?: number }).progress;
		return progress === undefined || progress < 100;
	});
	const src = useAttachmentSrc();

	// Show loading spinner only when actively processing (not when done and waiting for send)
	if (isProcessing) {
		return (
			<div className="flex h-full w-full items-center justify-center bg-muted">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	return (
		<Avatar className="aui-attachment-tile-avatar h-full w-full rounded-none">
			<AvatarImage
				src={src}
				alt="Attachment preview"
				className="aui-attachment-tile-image object-cover"
			/>
			<AvatarFallback delayMs={isImage ? 200 : 0}>
				<FileText className="aui-attachment-tile-fallback-icon size-8 text-muted-foreground" />
			</AvatarFallback>
		</Avatar>
	);
};

const AttachmentUI: FC = () => {
	const api = useAssistantApi();
	const isComposer = api.attachment.source === "composer";

	const isImage = useAssistantState(({ attachment }) => attachment?.type === "image");
	// Check if actively processing (running AND progress < 100)
	// When progress is 100, processing is done but waiting for send()
	const isProcessing = useAssistantState(({ attachment }) => {
		const status = attachment?.status;
		if (status?.type !== "running") return false;
		const progress = (status as { type: "running"; progress?: number }).progress;
		return progress === undefined || progress < 100;
	});
	const typeLabel = useAssistantState(({ attachment }) => {
		const type = attachment?.type;
		switch (type) {
			case "image":
				return "Image";
			case "document":
				return "Document";
			case "file":
				return "File";
			default:
				return "File"; // Default fallback for unknown types
		}
	});

	return (
		<Tooltip>
			<AttachmentPrimitive.Root
				className={cn(
					"aui-attachment-root relative",
					isImage && "aui-attachment-root-composer only:[&>#attachment-tile]:size-24"
				)}
			>
				<AttachmentPreviewDialog>
					<TooltipTrigger asChild>
						<button
							type="button"
							className={cn(
								"aui-attachment-tile size-14 cursor-pointer overflow-hidden rounded-[14px] border bg-muted transition-opacity hover:opacity-75",
								isComposer && "aui-attachment-tile-composer border-foreground/20",
								isProcessing && "animate-pulse"
							)}
							id="attachment-tile"
							aria-label={isProcessing ? "Processing attachment..." : `${typeLabel} attachment`}
						>
							<AttachmentThumb />
						</button>
					</TooltipTrigger>
				</AttachmentPreviewDialog>
				{isComposer && !isProcessing && <AttachmentRemove />}
			</AttachmentPrimitive.Root>
			<TooltipContent
				side="top"
				className="bg-black text-white font-medium shadow-xl px-3 py-1.5 dark:bg-zinc-800 dark:text-zinc-50 border-none"
			>
				{isProcessing ? (
					<span className="flex items-center gap-1.5">
						<Spinner size="xs" />
						Processing...
					</span>
				) : (
					<AttachmentPrimitive.Name />
				)}
			</TooltipContent>
		</Tooltip>
	);
};

const AttachmentRemove: FC = () => {
	return (
		<AttachmentPrimitive.Remove asChild>
			<TooltipIconButton
				tooltip="Remove file"
				className="aui-attachment-tile-remove absolute top-1.5 right-1.5 size-3.5 rounded-full bg-white text-muted-foreground opacity-100 shadow-sm hover:bg-white! [&_svg]:text-black hover:[&_svg]:text-destructive"
				side="top"
			>
				<XIcon className="aui-attachment-remove-icon size-3 dark:stroke-[2.5px]" />
			</TooltipIconButton>
		</AttachmentPrimitive.Remove>
	);
};

/**
 * Image attachment with preview thumbnail (click to expand)
 */
const MessageImageAttachment: FC = () => {
	const attachmentName = useAssistantState(({ attachment }) => attachment?.name || "Image");
	const src = useAttachmentSrc();

	if (!src) return null;

	return (
		<AttachmentPreviewDialog>
			<div
				className="relative group cursor-pointer overflow-hidden rounded-xl border border-border/50 bg-muted transition-all hover:border-primary/30 hover:shadow-md"
				title={`Click to expand: ${attachmentName}`}
			>
				<Image
					src={src}
					alt={attachmentName}
					width={120}
					height={90}
					className="object-cover w-[120px] h-[90px] transition-transform group-hover:scale-105"
				/>
				{/* Hover overlay with filename */}
				<div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
					<div className="absolute bottom-1.5 left-1.5 right-1.5">
						<span className="text-[10px] text-white/90 font-medium truncate block">
							{attachmentName}
						</span>
					</div>
				</div>
			</div>
		</AttachmentPreviewDialog>
	);
};

/**
 * Document/file attachment as chip (similar to mentioned documents)
 */
const MessageDocumentAttachment: FC = () => {
	const attachmentName = useAssistantState(({ attachment }) => attachment?.name || "Attachment");

	return (
		<AttachmentPreviewDialog>
			<span
				className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-xs font-medium text-primary border border-primary/20 cursor-pointer hover:bg-primary/20 transition-colors"
				title={attachmentName}
			>
				<FileText className="size-3" />
				<span className="max-w-[150px] truncate">{attachmentName}</span>
			</span>
		</AttachmentPreviewDialog>
	);
};

/**
 * Attachment component for user messages
 * Shows image preview for images, chip for documents
 */
const MessageAttachmentChip: FC = () => {
	const isImage = useAssistantState(({ attachment }) => attachment?.type === "image");

	if (isImage) {
		return <MessageImageAttachment />;
	}

	return <MessageDocumentAttachment />;
};

export const UserMessageAttachments: FC = () => {
	return <MessagePrimitive.Attachments components={{ Attachment: MessageAttachmentChip }} />;
};

export const ComposerAttachments: FC = () => {
	return (
		<div className="aui-composer-attachments mb-2 flex w-full flex-row items-center gap-2 overflow-x-auto px-1.5 pt-0.5 pb-1 empty:hidden">
			<ComposerPrimitive.Attachments components={{ Attachment: AttachmentUI }} />
		</div>
	);
};

export const ComposerAddAttachment: FC = () => {
	const chatAttachmentInputRef = useRef<HTMLInputElement>(null);
	const { openDialog } = useDocumentUploadDialog();

	const handleFileUpload = () => {
		openDialog();
	};

	const handleChatAttachment = () => {
		chatAttachmentInputRef.current?.click();
	};

	// Prevent event bubbling when file input is clicked
	const handleFileInputClick = (e: React.MouseEvent<HTMLInputElement>) => {
		e.stopPropagation();
	};

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<TooltipIconButton
						tooltip="Upload"
						side="bottom"
						variant="ghost"
						size="icon"
						className="aui-composer-add-attachment size-[34px] rounded-full p-1 font-semibold text-xs hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30"
						aria-label="Upload"
					>
						<PlusIcon className="aui-attachment-add-icon size-5 stroke-[1.5px]" />
					</TooltipIconButton>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="start" className="w-48 bg-background border-border">
					<DropdownMenuItem onSelect={handleChatAttachment} className="cursor-pointer">
						<Paperclip className="size-4" />
						<span>Add attachment</span>
					</DropdownMenuItem>
					<DropdownMenuItem onClick={handleFileUpload} className="cursor-pointer">
						<Upload className="size-4" />
						<span>Upload Documents</span>
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			<ComposerPrimitive.AddAttachment asChild>
				<input
					ref={chatAttachmentInputRef}
					type="file"
					multiple
					className="hidden"
					accept="image/*,application/pdf,.doc,.docx,.txt"
					onClick={handleFileInputClick}
				/>
			</ComposerPrimitive.AddAttachment>
		</>
	);
};
