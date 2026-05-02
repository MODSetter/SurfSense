"use client";

import type { PlateElementProps } from "platejs/react";
import {
	createPlatePlugin,
	ParagraphPlugin,
	Plate,
	PlateContent,
	usePlateEditor,
} from "platejs/react";
import { type FC, forwardRef, useCallback, useImperativeHandle, useMemo, useRef } from "react";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { Document } from "@/contracts/types/document.types";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { cn } from "@/lib/utils";

export interface MentionedDocument {
	id: number;
	title: string;
	document_type?: string;
}

export interface InlineMentionEditorRef {
	focus: () => void;
	clear: () => void;
	setText: (text: string) => void;
	getText: () => string;
	getMentionedDocuments: () => MentionedDocument[];
	insertDocumentChip: (
		doc: Pick<Document, "id" | "title" | "document_type">,
		options?: { removeTriggerText?: boolean }
	) => void;
	removeDocumentChip: (docId: number, docType?: string) => void;
	setDocumentChipStatus: (
		docId: number,
		docType: string | undefined,
		statusLabel: string | null,
		statusKind?: "pending" | "processing" | "ready" | "failed"
	) => void;
}

interface InlineMentionEditorProps {
	placeholder?: string;
	onMentionTrigger?: (query: string) => void;
	onMentionClose?: () => void;
	onActionTrigger?: (query: string) => void;
	onActionClose?: () => void;
	onSubmit?: () => void;
	onChange?: (text: string, docs: MentionedDocument[]) => void;
	onDocumentRemove?: (docId: number, docType?: string) => void;
	onKeyDown?: (e: React.KeyboardEvent) => void;
	disabled?: boolean;
	className?: string;
	initialText?: string;
}

type MentionStatusKind = "pending" | "processing" | "ready" | "failed";
type ComposerTextNode = { text: string };
type MentionElementNode = {
	type: "mention";
	id: number;
	title: string;
	document_type?: string;
	statusLabel?: string | null;
	statusKind?: MentionStatusKind;
	children: [{ text: "" }];
};
type ComposerNode = ComposerTextNode | MentionElementNode;
type ComposerParagraph = { type: "p"; children: ComposerNode[] };
type ComposerValue = ComposerParagraph[];

const MENTION_TYPE = "mention";
const MENTION_CHIP_CLASSNAME =
	"inline-flex h-5 items-center gap-1 mx-0.5 rounded bg-primary/10 px-1 text-xs font-bold text-primary/60 select-none align-middle leading-none";
const MENTION_CHIP_ICON_CLASSNAME = "flex items-center text-muted-foreground leading-none";
const MENTION_CHIP_TITLE_CLASSNAME = "max-w-[120px] truncate leading-none";
const COMPOSER_TEXT_METRICS_CLASSNAME = "text-sm leading-6";

const EMPTY_VALUE: ComposerValue = [{ type: "p", children: [{ text: "" }] }];

const MentionElement: FC<PlateElementProps<MentionElementNode>> = ({
	attributes,
	children,
	element,
}) => {
	const statusClass =
		element.statusKind === "failed"
			? "text-destructive"
			: element.statusKind === "ready"
				? "text-emerald-700"
				: "text-amber-700";

	return (
		<span {...attributes} className="inline-flex align-middle">
			<span contentEditable={false} className={`${MENTION_CHIP_CLASSNAME} cursor-default`}>
				<span className={MENTION_CHIP_ICON_CLASSNAME}>
					{getConnectorIcon(element.document_type ?? "UNKNOWN", "h-3 w-3")}
				</span>
				<span className={MENTION_CHIP_TITLE_CLASSNAME} title={element.title}>
					{element.title}
				</span>
				{element.statusLabel ? (
					<span className={cn("text-[10px] font-semibold opacity-80", statusClass)}>
						{element.statusLabel}
					</span>
				) : null}
			</span>
			{children}
		</span>
	);
};

const MentionPlugin = createPlatePlugin({
	key: MENTION_TYPE,
	node: {
		isElement: true,
		isInline: true,
		isVoid: true,
		type: MENTION_TYPE,
		component: MentionElement,
	},
});

function isMentionNode(node: ComposerNode): node is MentionElementNode {
	return typeof node === "object" && "type" in node && node.type === MENTION_TYPE;
}

function getTextNode(node: ComposerNode): ComposerTextNode | null {
	if (typeof node === "object" && "text" in node && typeof node.text === "string") return node;
	return null;
}

function toValueFromText(text: string): ComposerValue {
	const lines = text.split("\n");
	if (lines.length === 0) return EMPTY_VALUE;
	return lines.map((line) => ({ type: "p", children: [{ text: line }] })) as ComposerValue;
}

function getPlainText(value: ComposerValue): string {
	const lines = value.map((block) =>
		block.children
			.map((node) => {
				if (isMentionNode(node)) return `@${node.title}`;
				return getTextNode(node)?.text ?? "";
			})
			.join("")
	);
	return lines.join("\n").trim();
}

function getMentionedDocuments(value: ComposerValue): MentionedDocument[] {
	const map = new Map<string, MentionedDocument>();
	for (const block of value) {
		for (const node of block.children) {
			if (!isMentionNode(node)) continue;
			const doc: MentionedDocument = {
				id: node.id,
				title: node.title,
				document_type: node.document_type,
			};
			map.set(getMentionDocKey(doc), doc);
		}
	}
	return Array.from(map.values());
}

type EditorSelection = {
	anchor: { path: number[]; offset: number };
	focus: { path: number[]; offset: number };
} | null;

function getCursorTextContext(value: ComposerValue, selection: EditorSelection) {
	if (!selection || !selection.anchor || !selection.focus) return null;
	if (
		selection.anchor.path.length < 2 ||
		selection.focus.path.length < 2 ||
		selection.anchor.path[0] !== selection.focus.path[0] ||
		selection.anchor.path[1] !== selection.focus.path[1]
	) {
		return null;
	}

	const block = value[selection.anchor.path[0]];
	if (!block) return null;
	const child = block.children[selection.anchor.path[1]];
	const textNode = getTextNode(child);
	if (!textNode) return null;

	return {
		blockIndex: selection.anchor.path[0],
		childIndex: selection.anchor.path[1],
		text: textNode.text,
		cursor: selection.anchor.offset,
	};
}

function scanActiveTrigger(text: string, cursor: number) {
	let wordStart = 0;
	for (let i = cursor - 1; i >= 0; i--) {
		if (text[i] === " " || text[i] === "\n") {
			wordStart = i + 1;
			break;
		}
	}

	let triggerChar: "@" | "/" | null = null;
	let triggerIndex = -1;
	for (let i = wordStart; i < cursor; i++) {
		if (text[i] === "@" || text[i] === "/") {
			triggerChar = text[i] as "@" | "/";
			triggerIndex = i;
			break;
		}
	}
	if (!triggerChar || triggerIndex === -1) return null;

	const query = text.slice(triggerIndex + 1, cursor);
	if (query.startsWith(" ")) return null;
	if (
		triggerChar === "/" &&
		triggerIndex > 0 &&
		text[triggerIndex - 1] !== " " &&
		text[triggerIndex - 1] !== "\n"
	) {
		return null;
	}

	return { triggerChar, query };
}

export const InlineMentionEditor = forwardRef<InlineMentionEditorRef, InlineMentionEditorProps>(
	(
		{
			placeholder = "Type @ to mention documents...",
			onMentionTrigger,
			onMentionClose,
			onActionTrigger,
			onActionClose,
			onSubmit,
			onChange,
			onDocumentRemove,
			onKeyDown,
			disabled = false,
			className,
			initialText,
		},
		ref
	) => {
		const editableRef = useRef<HTMLDivElement | null>(null);
		const editor = usePlateEditor({
			readOnly: disabled,
			plugins: [ParagraphPlugin, MentionPlugin],
			value: initialText ? toValueFromText(initialText) : EMPTY_VALUE,
		});

		const focusAtEnd = useCallback(() => {
			const el = editableRef.current;
			if (!el) return;
			el.focus();
			const selection = window.getSelection();
			const range = document.createRange();
			range.selectNodeContents(el);
			range.collapse(false);
			selection?.removeAllRanges();
			selection?.addRange(range);
		}, []);

		const getCurrentValue = useCallback(
			() => (editor.children as ComposerValue) ?? EMPTY_VALUE,
			[editor]
		);

		const emitState = useCallback(
			(nextValue: ComposerValue) => {
				const text = getPlainText(nextValue);
				const docs = getMentionedDocuments(nextValue);
				onChange?.(text, docs);

				const cursorCtx = getCursorTextContext(nextValue, editor.selection);
				if (!cursorCtx) {
					onMentionClose?.();
					onActionClose?.();
					return;
				}

				const trigger = scanActiveTrigger(cursorCtx.text, cursorCtx.cursor);
				if (!trigger) {
					onMentionClose?.();
					onActionClose?.();
					return;
				}

				if (trigger.triggerChar === "@") {
					onMentionTrigger?.(trigger.query);
					onActionClose?.();
					return;
				}

				onActionTrigger?.(trigger.query);
				onMentionClose?.();
			},
			[editor.selection, onActionClose, onActionTrigger, onChange, onMentionClose, onMentionTrigger]
		);

		const setValue = useCallback(
			(nextValue: ComposerValue) => {
				const tf = editor.tf as { setValue: (value: ComposerValue) => void };
				tf.setValue(nextValue);
				emitState(nextValue);
			},
			[editor, emitState]
		);

		const insertDocumentChip = useCallback(
			(
				doc: Pick<Document, "id" | "title" | "document_type">,
				options?: { removeTriggerText?: boolean }
			) => {
				if (typeof doc.id !== "number" || typeof doc.title !== "string") return;

				const removeTriggerText = options?.removeTriggerText ?? true;
				const current = getCurrentValue();
				const selection = editor.selection;
				const mentionNode: MentionElementNode = {
					type: MENTION_TYPE,
					id: doc.id,
					title: doc.title,
					document_type: doc.document_type,
					children: [{ text: "" }],
				};

				const cursorCtx = getCursorTextContext(current, selection);
				if (!cursorCtx) {
					const lastBlock = current[current.length - 1] ?? { type: "p", children: [{ text: "" }] };
					const appended: ComposerValue = [
						...current.slice(0, -1),
						{
							...lastBlock,
							children: [...lastBlock.children, mentionNode, { text: " " }],
						},
					];
					setValue(appended);
					requestAnimationFrame(focusAtEnd);
					return;
				}

				const block = current[cursorCtx.blockIndex];
				const currentChild = getTextNode(block.children[cursorCtx.childIndex]);
				if (!currentChild) {
					const children = [...block.children];
					children.splice(cursorCtx.childIndex + 1, 0, mentionNode, { text: " " });
					const next = [...current];
					next[cursorCtx.blockIndex] = { ...block, children };
					setValue(next as ComposerValue);
					requestAnimationFrame(focusAtEnd);
					return;
				}

				const text = currentChild.text;
				let removeStart = cursorCtx.cursor;
				if (removeTriggerText) {
					for (let i = cursorCtx.cursor - 1; i >= 0; i--) {
						if (text[i] === "@") {
							removeStart = i;
							break;
						}
						if (text[i] === " " || text[i] === "\n") break;
					}
				}

				const before = text.slice(0, removeStart);
				const after = text.slice(cursorCtx.cursor);
				const replacement: ComposerNode[] = [];
				if (before.length > 0) replacement.push({ text: before });
				replacement.push(mentionNode);
				replacement.push({ text: ` ${after}` });

				const children = [...block.children];
				children.splice(cursorCtx.childIndex, 1, ...replacement);
				const next = [...current];
				next[cursorCtx.blockIndex] = { ...block, children };
				setValue(next as ComposerValue);
				requestAnimationFrame(focusAtEnd);
			},
			[editor.selection, focusAtEnd, getCurrentValue, setValue]
		);

		const removeDocumentChip = useCallback(
			(docId: number, docType?: string) => {
				const current = getCurrentValue();
				let changed = false;
				const next = current.map((block) => {
					const children = block.children.filter((node) => {
						if (!isMentionNode(node)) return true;
						const match =
							node.id === docId && (node.document_type ?? "UNKNOWN") === (docType ?? "UNKNOWN");
						if (match) changed = true;
						return !match;
					});
					return { ...block, children: children.length ? children : [{ text: "" }] };
				});
				if (!changed) return;
				setValue(next as ComposerValue);
			},
			[getCurrentValue, setValue]
		);

		const setDocumentChipStatus = useCallback(
			(
				docId: number,
				docType: string | undefined,
				statusLabel: string | null,
				statusKind: MentionStatusKind = "pending"
			) => {
				const current = getCurrentValue();
				let changed = false;
				const next = current.map((block) => ({
					...block,
					children: block.children.map((node) => {
						if (!isMentionNode(node)) return node;
						const sameType = (node.document_type ?? "UNKNOWN") === (docType ?? "UNKNOWN");
						if (node.id !== docId || !sameType) return node;
						changed = true;
						return {
							...node,
							statusLabel,
							statusKind: statusLabel ? statusKind : undefined,
						};
					}),
				}));
				if (!changed) return;
				setValue(next as ComposerValue);
			},
			[getCurrentValue, setValue]
		);

		const clear = useCallback(() => {
			setValue(EMPTY_VALUE);
		}, [setValue]);

		const setText = useCallback(
			(text: string) => {
				setValue(toValueFromText(text));
				requestAnimationFrame(focusAtEnd);
			},
			[focusAtEnd, setValue]
		);

		const getText = useCallback(() => getPlainText(getCurrentValue()), [getCurrentValue]);
		const getMentionedDocs = useCallback(
			() => getMentionedDocuments(getCurrentValue()),
			[getCurrentValue]
		);

		useImperativeHandle(
			ref,
			() => ({
				focus: () => editableRef.current?.focus(),
				clear,
				setText,
				getText,
				getMentionedDocuments: getMentionedDocs,
				insertDocumentChip,
				removeDocumentChip,
				setDocumentChipStatus,
			}),
			[
				clear,
				getMentionedDocs,
				getText,
				insertDocumentChip,
				removeDocumentChip,
				setDocumentChipStatus,
				setText,
			]
		);

		const handleKeyDown = useCallback(
			(e: React.KeyboardEvent<HTMLDivElement>) => {
				onKeyDown?.(e);
				if (e.defaultPrevented) return;

				if (e.key === "Enter" && !e.shiftKey) {
					e.preventDefault();
					onSubmit?.();
					return;
				}

				if (e.key !== "Backspace") return;
				const selection = editor.selection;
				if (!selection || !selection.anchor || !selection.focus) return;
				if (
					selection.anchor.path.length < 2 ||
					selection.focus.path.length < 2 ||
					selection.anchor.path[0] !== selection.focus.path[0]
				) {
					return;
				}
				if (selection.anchor.offset !== 0 || selection.focus.offset !== 0) return;

				const value = getCurrentValue();
				const block = value[selection.anchor.path[0]];
				if (!block) return;
				const childIndex = selection.anchor.path[1];
				if (childIndex <= 0) return;
				const prev = block.children[childIndex - 1];
				if (!isMentionNode(prev)) return;

				e.preventDefault();
				removeDocumentChip(prev.id, prev.document_type);
				onDocumentRemove?.(prev.id, prev.document_type);
			},
			[editor.selection, getCurrentValue, onDocumentRemove, onKeyDown, onSubmit, removeDocumentChip]
		);

		const editableProps = useMemo(
			() => ({
				placeholder,
				onPaste: (e: React.ClipboardEvent<HTMLDivElement>) => {
					e.preventDefault();
					const text = e.clipboardData.getData("text/plain");
					const tf = editor.tf as { insertText: (value: string) => void };
					tf.insertText(text);
				},
				onKeyDown: handleKeyDown,
			}),
			[editor, handleKeyDown, placeholder]
		);

		return (
			<div className="relative w-full">
				<Plate
					editor={editor}
					onChange={({ value }) => {
						emitState(value as ComposerValue);
					}}
				>
					<PlateContent
						ref={editableRef}
						readOnly={disabled}
						{...editableProps}
						className={cn(
							"min-h-[24px] max-h-32 overflow-y-auto outline-none whitespace-pre-wrap wrap-break-word",
							COMPOSER_TEXT_METRICS_CLASSNAME,
							disabled && "opacity-50 cursor-not-allowed",
							className
						)}
					/>
				</Plate>
			</div>
		);
	}
);

InlineMentionEditor.displayName = "InlineMentionEditor";
