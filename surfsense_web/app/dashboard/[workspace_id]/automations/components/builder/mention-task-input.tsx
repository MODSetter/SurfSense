"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MentionedDocumentInfo } from "@/atoms/chat/mentioned-documents.atom";
import {
	InlineMentionEditor,
	type InlineMentionEditorRef,
	type MentionChipInput,
	type MentionedDocument,
	type SuggestionAnchorRect,
	type SuggestionTriggerInfo,
} from "@/components/assistant-ui/inline-mention-editor";
import { ComposerSuggestionPopoverContent } from "@/components/new-chat/composer-suggestion-popup";
import {
	DocumentMentionPicker,
	type DocumentMentionPickerRef,
} from "@/components/new-chat/document-mention-picker";
import { Popover, PopoverAnchor } from "@/components/ui/popover";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { cn } from "@/lib/utils";

interface MentionTaskInputProps {
	workspaceId: number;
	value: string;
	mentions: MentionedDocumentInfo[];
	onChange: (text: string, mentions: MentionedDocumentInfo[]) => void;
	placeholder?: string;
	disabled?: boolean;
}

type AnchorPoint = { left: number; top: number };

// Mirror of thread.tsx's getComposerSuggestionAnchorPoint -- kept local so the
// chat composer stays untouched.
function getAnchorPoint(rect: SuggestionAnchorRect | null): AnchorPoint | null {
	if (!rect) return null;
	return { left: rect.left, top: rect.bottom };
}

/** Project the editor's chip shape into the canonical mention info union. */
function toMentionInfo(doc: MentionedDocument): MentionedDocumentInfo {
	if (doc.kind === "connector") {
		return {
			id: doc.id,
			title: doc.title,
			kind: "connector",
			connector_type: doc.connector_type ?? "UNKNOWN",
			account_name: doc.account_name ?? doc.title,
		};
	}
	if (doc.kind === "folder") {
		return { id: doc.id, title: doc.title, kind: "folder" };
	}
	return {
		id: doc.id,
		title: doc.title,
		document_type: doc.document_type ?? "UNKNOWN",
		kind: "doc",
	};
}

/** Project a mention info into the editor's chip-insertion shape. */
function toChipInput(mention: MentionedDocumentInfo): MentionChipInput {
	if (mention.kind === "connector") {
		return {
			id: mention.id,
			title: mention.title,
			kind: "connector",
			connector_type: mention.connector_type,
			account_name: mention.account_name,
		};
	}
	if (mention.kind === "folder") {
		return { id: mention.id, title: mention.title, kind: "folder" };
	}
	if (mention.kind === "thread") {
		return { id: mention.id, title: mention.title, kind: "thread" };
	}
	return {
		id: mention.id,
		title: mention.title,
		kind: "doc",
		document_type: mention.document_type,
	};
}

function removeFirstToken(text: string, token: string): string {
	const index = text.indexOf(token);
	if (index === -1) return text;
	return text.slice(0, index) + text.slice(index + token.length);
}

/**
 * Task input that reuses the chat ``@`` mention experience -- the same
 * ``InlineMentionEditor`` + ``DocumentMentionPicker`` as the composer. The
 * editor is the source of truth while mounted; ``onChange`` reports both the
 * plain text (chips rendered as ``@Title``) and the structured mention list
 * so the builder can persist IDs for the run.
 */
export function MentionTaskInput({
	workspaceId,
	value,
	mentions,
	onChange,
	placeholder,
	disabled,
}: MentionTaskInputProps) {
	const editorRef = useRef<InlineMentionEditorRef>(null);
	const pickerRef = useRef<DocumentMentionPickerRef>(null);

	const [showPopover, setShowPopover] = useState(false);
	const [mentionQuery, setMentionQuery] = useState("");
	const [anchorPoint, setAnchorPoint] = useState<AnchorPoint | null>(null);

	// One-shot hydration of existing mentions into real chips. ``initialText``
	// seeds the literal ``@Title`` text; here we strip those tokens and
	// re-insert them as chips so the editor reports the structured docs (and
	// editing can't silently drop the mention IDs). Position isn't preserved
	// on re-hydration -- chips append after the remaining prose.
	const didHydrateRef = useRef(false);
	useEffect(() => {
		if (didHydrateRef.current) return;
		didHydrateRef.current = true;
		if (mentions.length === 0) return;
		const editor = editorRef.current;
		if (!editor) return;

		let baseText = value;
		for (const mention of mentions) {
			baseText = removeFirstToken(baseText, `@${mention.title}`);
		}
		baseText = baseText.replace(/[ \t]{2,}/g, " ").trim();
		editor.setText(baseText);
		for (const mention of mentions) {
			editor.insertMentionChip(toChipInput(mention), { removeTriggerText: false });
		}
	}, [mentions, value]);

	const closePopover = useCallback(() => {
		setShowPopover(false);
		setMentionQuery("");
		setAnchorPoint(null);
	}, []);

	const handleEditorChange = useCallback(
		(text: string, docs: MentionedDocument[]) => {
			onChange(text, docs.map(toMentionInfo));
		},
		[onChange]
	);

	const handleMentionTrigger = useCallback((trigger: SuggestionTriggerInfo) => {
		const point = getAnchorPoint(trigger.anchorRect);
		if (!point) {
			setShowPopover(false);
			setMentionQuery("");
			setAnchorPoint(null);
			return;
		}
		setAnchorPoint((current) => current ?? point);
		setShowPopover(true);
		setMentionQuery(trigger.query);
	}, []);

	const handleMentionClose = useCallback(() => {
		setShowPopover((open) => {
			if (open) {
				setMentionQuery("");
				setAnchorPoint(null);
			}
			return false;
		});
	}, []);

	const handlePopoverOpenChange = useCallback((open: boolean) => {
		setShowPopover(open);
		if (!open) {
			setMentionQuery("");
			setAnchorPoint(null);
		}
	}, []);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (!showPopover) return;
			if (e.key === "ArrowDown") {
				e.preventDefault();
				pickerRef.current?.moveDown();
			} else if (e.key === "ArrowUp") {
				e.preventDefault();
				pickerRef.current?.moveUp();
			} else if (e.key === "Enter") {
				e.preventDefault();
				pickerRef.current?.selectHighlighted();
			} else if (e.key === "Escape") {
				e.preventDefault();
				if (pickerRef.current?.goBack()) return;
				closePopover();
			}
		},
		[showPopover, closePopover]
	);

	const handleSelection = useCallback(
		(picked: MentionedDocumentInfo[]) => {
			const editor = editorRef.current;
			const existing = new Set(
				(editor?.getMentionedDocuments() ?? []).map((doc) => getMentionDocKey(doc))
			);
			for (const mention of picked) {
				const key = getMentionDocKey(mention);
				if (existing.has(key)) continue;
				editor?.insertMentionChip(toChipInput(mention));
				existing.add(key);
			}
			closePopover();
		},
		[closePopover]
	);

	return (
		<div
			className={cn(
				"border-popover-border focus-within:border-ring focus-within:ring-ring/50 dark:bg-input/30 min-h-16 w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-within:ring-[3px]",
				disabled && "cursor-not-allowed opacity-50"
			)}
		>
			<Popover open={showPopover} onOpenChange={handlePopoverOpenChange}>
				{anchorPoint ? (
					<>
						<PopoverAnchor
							className="pointer-events-none fixed size-0"
							style={{ left: anchorPoint.left, top: anchorPoint.top }}
						/>
						<ComposerSuggestionPopoverContent side="bottom">
							<DocumentMentionPicker
								ref={pickerRef}
								workspaceId={workspaceId}
								onSelectionChange={handleSelection}
								onDone={closePopover}
								initialSelectedDocuments={mentions}
								externalSearch={mentionQuery}
							/>
						</ComposerSuggestionPopoverContent>
					</>
				) : null}
			</Popover>
			<InlineMentionEditor
				ref={editorRef}
				initialText={value}
				placeholder={placeholder ?? "Type @ to reference files, folders, or connectors"}
				disabled={disabled}
				onChange={handleEditorChange}
				onMentionTrigger={handleMentionTrigger}
				onMentionClose={handleMentionClose}
				onKeyDown={handleKeyDown}
			/>
		</div>
	);
}
