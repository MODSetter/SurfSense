import { ComposerPrimitive, useAssistantState, useComposerRuntime } from "@assistant-ui/react";
import { useAtom, useSetAtom } from "jotai";
import { useParams } from "next/navigation";
import type { FC } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
	mentionedDocumentIdsAtom,
	mentionedDocumentsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { ComposerAddAttachment, ComposerAttachments } from "@/components/assistant-ui/attachment";
import { ComposerAction } from "@/components/assistant-ui/composer-action";
import {
	InlineMentionEditor,
	type InlineMentionEditorRef,
} from "@/components/assistant-ui/inline-mention-editor";
import {
	DocumentMentionPicker,
	type DocumentMentionPickerRef,
} from "@/components/new-chat/document-mention-picker";
import type { Document } from "@/contracts/types/document.types";

export const Composer: FC = () => {
	// ---- State for document mentions (using atoms to persist across remounts) ----
	const [mentionedDocuments, setMentionedDocuments] = useAtom(mentionedDocumentsAtom);
	const [showDocumentPopover, setShowDocumentPopover] = useState(false);
	const [mentionQuery, setMentionQuery] = useState("");
	const editorRef = useRef<InlineMentionEditorRef>(null);
	const editorContainerRef = useRef<HTMLDivElement>(null);
	const documentPickerRef = useRef<DocumentMentionPickerRef>(null);
	const { search_space_id } = useParams();
	const setMentionedDocumentIds = useSetAtom(mentionedDocumentIdsAtom);
	const composerRuntime = useComposerRuntime();
	const hasAutoFocusedRef = useRef(false);

	// Check if thread is empty (new chat)
	const isThreadEmpty = useAssistantState(({ thread }) => thread.isEmpty);

	// Check if thread is currently running (streaming response)
	const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);

	// Auto-focus editor when on new chat page
	useEffect(() => {
		if (isThreadEmpty && !hasAutoFocusedRef.current && editorRef.current) {
			// Small delay to ensure the editor is fully mounted
			const timeoutId = setTimeout(() => {
				editorRef.current?.focus();
				hasAutoFocusedRef.current = true;
			}, 100);
			return () => clearTimeout(timeoutId);
		}
	}, [isThreadEmpty]);

	// Sync mentioned document IDs to atom for use in chat request
	useEffect(() => {
		setMentionedDocumentIds({
			surfsense_doc_ids: mentionedDocuments
				.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
				.map((doc) => doc.id),
			document_ids: mentionedDocuments
				.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
				.map((doc) => doc.id),
		});
	}, [mentionedDocuments, setMentionedDocumentIds]);

	// Handle text change from inline editor - sync with assistant-ui composer
	const handleEditorChange = useCallback(
		(text: string) => {
			composerRuntime.setText(text);
		},
		[composerRuntime]
	);

	// Handle @ mention trigger from inline editor
	const handleMentionTrigger = useCallback((query: string) => {
		setShowDocumentPopover(true);
		setMentionQuery(query);
	}, []);

	// Handle mention close
	const handleMentionClose = useCallback(() => {
		if (showDocumentPopover) {
			setShowDocumentPopover(false);
			setMentionQuery("");
		}
	}, [showDocumentPopover]);

	// Handle keyboard navigation when popover is open
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (showDocumentPopover) {
				if (e.key === "ArrowDown") {
					e.preventDefault();
					documentPickerRef.current?.moveDown();
					return;
				}
				if (e.key === "ArrowUp") {
					e.preventDefault();
					documentPickerRef.current?.moveUp();
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					documentPickerRef.current?.selectHighlighted();
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					setShowDocumentPopover(false);
					setMentionQuery("");
					return;
				}
			}
		},
		[showDocumentPopover]
	);

	// Handle submit from inline editor (Enter key)
	const handleSubmit = useCallback(() => {
		// Prevent sending while a response is still streaming
		if (isThreadRunning) {
			return;
		}
		if (!showDocumentPopover) {
			composerRuntime.send();
			// Clear the editor after sending
			editorRef.current?.clear();
			setMentionedDocuments([]);
			setMentionedDocumentIds({
				surfsense_doc_ids: [],
				document_ids: [],
			});
		}
	}, [
		showDocumentPopover,
		isThreadRunning,
		composerRuntime,
		setMentionedDocuments,
		setMentionedDocumentIds,
	]);

	const handleDocumentRemove = useCallback(
		(docId: number, docType?: string) => {
			setMentionedDocuments((prev) => {
				const updated = prev.filter((doc) => !(doc.id === docId && doc.document_type === docType));
				setMentionedDocumentIds({
					surfsense_doc_ids: updated
						.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
						.map((doc) => doc.id),
					document_ids: updated
						.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
						.map((doc) => doc.id),
				});
				return updated;
			});
		},
		[setMentionedDocuments, setMentionedDocumentIds]
	);

	const handleDocumentsMention = useCallback(
		(documents: Pick<Document, "id" | "title" | "document_type">[]) => {
			const existingKeys = new Set(mentionedDocuments.map((d) => `${d.document_type}:${d.id}`));
			const newDocs = documents.filter(
				(doc) => !existingKeys.has(`${doc.document_type}:${doc.id}`)
			);

			for (const doc of newDocs) {
				editorRef.current?.insertDocumentChip(doc);
			}

			setMentionedDocuments((prev) => {
				const existingKeySet = new Set(prev.map((d) => `${d.document_type}:${d.id}`));
				const uniqueNewDocs = documents.filter(
					(doc) => !existingKeySet.has(`${doc.document_type}:${doc.id}`)
				);
				const updated = [...prev, ...uniqueNewDocs];
				setMentionedDocumentIds({
					surfsense_doc_ids: updated
						.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
						.map((doc) => doc.id),
					document_ids: updated
						.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
						.map((doc) => doc.id),
				});
				return updated;
			});

			setMentionQuery("");
		},
		[mentionedDocuments, setMentionedDocuments, setMentionedDocumentIds]
	);

	return (
		<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
			<ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone flex w-full flex-col rounded-2xl border-input bg-muted px-1 pt-2 outline-none transition-shadow data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-accent/50">
				<ComposerAttachments />
				{/* -------- Inline Mention Editor -------- */}
				<div ref={editorContainerRef} className="aui-composer-input-wrapper px-3 pt-3 pb-6">
					<InlineMentionEditor
						ref={editorRef}
						placeholder="Ask SurfSense or @mention docs"
						onMentionTrigger={handleMentionTrigger}
						onMentionClose={handleMentionClose}
						onChange={handleEditorChange}
						onDocumentRemove={handleDocumentRemove}
						onSubmit={handleSubmit}
						onKeyDown={handleKeyDown}
						className="min-h-[24px]"
					/>
				</div>

				{/* -------- Document mention popover (rendered via portal) -------- */}
				{showDocumentPopover &&
					typeof document !== "undefined" &&
					createPortal(
						<>
							{/* Backdrop */}
							<button
								type="button"
								className="fixed inset-0 cursor-default"
								style={{ zIndex: 9998 }}
								onClick={() => setShowDocumentPopover(false)}
								aria-label="Close document picker"
							/>
							{/* Popover positioned above input */}
							<div
								className="fixed shadow-2xl rounded-lg border border-border overflow-hidden bg-popover"
								style={{
									zIndex: 9999,
									bottom: editorContainerRef.current
										? `${window.innerHeight - editorContainerRef.current.getBoundingClientRect().top + 8}px`
										: "200px",
									left: editorContainerRef.current
										? `${editorContainerRef.current.getBoundingClientRect().left}px`
										: "50%",
								}}
							>
								<DocumentMentionPicker
									ref={documentPickerRef}
									searchSpaceId={Number(search_space_id)}
									onSelectionChange={handleDocumentsMention}
									onDone={() => {
										setShowDocumentPopover(false);
										setMentionQuery("");
									}}
									initialSelectedDocuments={mentionedDocuments}
									externalSearch={mentionQuery}
								/>
							</div>
						</>,
						document.body
					)}
				<ComposerAction />
			</ComposerPrimitive.AttachmentDropzone>
		</ComposerPrimitive.Root>
	);
};
