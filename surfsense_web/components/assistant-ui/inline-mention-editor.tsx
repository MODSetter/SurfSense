"use client";

import { Folder as FolderIcon, X as XIcon } from "lucide-react";
import type { NodeEntry, TElement } from "platejs";
import type { PlateElementProps } from "platejs/react";
import {
	createPlatePlugin,
	ParagraphPlugin,
	Plate,
	PlateContent,
	usePlateEditor,
} from "platejs/react";
import {
	createContext,
	type FC,
	forwardRef,
	useCallback,
	useContext,
	useImperativeHandle,
	useMemo,
	useRef,
} from "react";
import { FOLDER_MENTION_DOCUMENT_TYPE } from "@/atoms/chat/mentioned-documents.atom";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { Document } from "@/contracts/types/document.types";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { cn } from "@/lib/utils";

export type MentionKind = "doc" | "folder";

export interface MentionedDocument {
	id: number;
	title: string;
	document_type?: string;
	kind: MentionKind;
}

/**
 * Input shape for inserting a chip. ``kind`` defaults to ``"doc"``
 * when omitted so legacy callers don't have to thread the
 * discriminator. Folder callers pass ``kind: "folder"`` and the
 * folder ``id`` and ``title``; ``document_type`` defaults to
 * ``FOLDER_MENTION_DOCUMENT_TYPE`` inside ``insertMentionChip`` so the
 * dedup key (`kind:document_type:id`) never collides with a doc chip
 * that happens to share an id.
 */
export type MentionChipInput = {
	id: number;
	title: string;
	document_type?: string;
	kind?: MentionKind;
};

export interface InlineMentionEditorRef {
	focus: () => void;
	clear: () => void;
	setText: (text: string) => void;
	getText: () => string;
	getMentionedDocuments: () => MentionedDocument[];
	insertMentionChip: (mention: MentionChipInput, options?: { removeTriggerText?: boolean }) => void;
	/**
	 * @deprecated Use ``insertMentionChip``. Kept for one transition
	 * cycle so we don't break ad-hoc callers; prefer the new name.
	 */
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
	/**
	 * Discriminator added so a folder chip and a doc chip with the
	 * same id round-trip cleanly through ``getMentionedDocuments``
	 * and the persisted ``mentioned-documents`` content part.
	 * Defaults to ``"doc"`` for nodes that predate this field.
	 */
	kind?: MentionKind;
	statusLabel?: string | null;
	statusKind?: MentionStatusKind;
	children: [{ text: "" }];
};
type ComposerNode = ComposerTextNode | MentionElementNode;
type ComposerParagraph = { type: "p"; children: ComposerNode[] };
type ComposerValue = ComposerParagraph[];

const MENTION_TYPE = "mention";
const MENTION_CHIP_CLASSNAME =
	"group inline-flex h-5 items-center gap-1 mx-0.5 rounded bg-primary/10 px-1 text-xs font-bold text-primary/60 select-none align-middle leading-none";
const MENTION_CHIP_ICON_CLASSNAME = "flex items-center text-muted-foreground leading-none";
const MENTION_CHIP_TITLE_CLASSNAME = "max-w-[120px] truncate leading-none";
const COMPOSER_TEXT_METRICS_CLASSNAME = "text-sm leading-6";

const EMPTY_VALUE: ComposerValue = [{ type: "p", children: [{ text: "" }] }];

/**
 * Internal seam that lets ``MentionElement`` (a Plate render component
 * with no React props beyond ``element``) reach the editor's chip-removal
 * function. Mirrors the Backspace path in ``handleKeyDown`` so the X
 * button delegates to the exact same combined call site — no extra
 * state, no atom coupling leaking into the chip.
 */
type MentionEditorContextValue = {
	removeChip: (docId: number, docType: string | undefined) => void;
};
const MentionEditorContext = createContext<MentionEditorContextValue | null>(null);

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

	const isFolder = element.kind === "folder";
	const ctx = useContext(MentionEditorContext);

	return (
		<span {...attributes} className="inline-flex align-middle">
			<span contentEditable={false} className={`${MENTION_CHIP_CLASSNAME} cursor-default`}>
				<span className={MENTION_CHIP_ICON_CLASSNAME}>
					<span className="relative flex h-3 w-3 items-center justify-center">
						<span className="flex items-center justify-center transition-opacity group-hover:opacity-0">
							{isFolder ? (
								<FolderIcon className="h-3 w-3" />
							) : (
								getConnectorIcon(element.document_type ?? "UNKNOWN", "h-3 w-3")
							)}
						</span>
						{ctx ? (
							<button
								type="button"
								aria-label={`Remove mention ${element.title}`}
								title={`Remove ${element.title}`}
								onMouseDown={(e) => e.preventDefault()}
								onClick={(e) => {
									e.stopPropagation();
									ctx.removeChip(element.id, element.document_type);
								}}
								className="absolute inset-0 flex items-center justify-center rounded-sm opacity-0 transition-opacity hover:text-primary focus-visible:opacity-100 focus-visible:outline-none group-hover:opacity-100"
							>
								<XIcon className="h-3 w-3" />
							</button>
						) : null}
					</span>
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
			const kind: MentionKind = node.kind ?? "doc";
			const doc: MentionedDocument = {
				id: node.id,
				title: node.title,
				document_type: node.document_type,
				kind,
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

		// Move the caret to the end of the document and focus the editor.
		// Routes through Plate's transforms so ``editor.selection`` and
		// the DOM selection stay in sync — bypassing Plate (via raw
		// ``window.getSelection``) was the prior implementation and is
		// what made the caret disappear after every ``setValue``-based
		// mutation. Falls back to DOM focus if Plate's API throws (e.g.
		// during a transient unmount race).
		const focusAtEnd = useCallback(() => {
			try {
				editor.tf.select(editor.api.end([]));
				editor.tf.focus();
			} catch {
				editableRef.current?.focus();
			}
		}, [editor]);

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

		// Insert a mention chip at the current caret. Uses Plate
		// transforms so Slate keeps the editor selection valid through
		// the edit.
		//
		// Critical detail: the chip is a void inline element. Inserting
		// it on its own with ``{ select: true }`` would land the caret
		// inside the void's empty ``children: [{ text: "" }]`` — a point
		// the browser can't render a caret on, which is what made the
		// cursor disappear or jump to the wrong side of the chip after
		// insertion. Inserting ``[mentionNode, { text: " " }]`` as a
		// single array means the *last* inserted node is a text node, so
		// ``{ select: true }`` resolves to that text node's end (offset
		// 1, after the trailing space) — a real, renderable text point.
		// The whole sequence stays inside ``withoutNormalizing`` so the
		// optional trigger-text delete and the chip insert show up as a
		// single undo step.
		const insertMentionChip = useCallback(
			(mention: MentionChipInput, options?: { removeTriggerText?: boolean }) => {
				if (typeof mention.id !== "number" || typeof mention.title !== "string") return;

				const removeTriggerText = options?.removeTriggerText ?? true;
				const kind: MentionKind = mention.kind ?? "doc";
				const document_type =
					mention.document_type ?? (kind === "folder" ? FOLDER_MENTION_DOCUMENT_TYPE : undefined);
				const mentionNode: MentionElementNode = {
					type: MENTION_TYPE,
					id: mention.id,
					title: mention.title,
					document_type,
					kind,
					children: [{ text: "" }],
				};

				editor.tf.withoutNormalizing(() => {
					const selection = editor.selection;

					// No active editor selection — typically because focus
					// moved to a picker/dropdown. Snap the caret to the end
					// of the document so the chip appends cleanly instead
					// of disappearing into a dead range.
					if (!selection) {
						editor.tf.select(editor.api.end([]));
					} else if (removeTriggerText) {
						// Delete the in-progress "@query" text so the chip
						// stands in for it. Mirrors the old splice but lets
						// Slate keep selection sane through the edit.
						const cursorCtx = getCursorTextContext(getCurrentValue(), selection);
						if (cursorCtx) {
							const text = cursorCtx.text;
							let triggerIndex = -1;
							for (let i = cursorCtx.cursor - 1; i >= 0; i--) {
								if (text[i] === "@") {
									triggerIndex = i;
									break;
								}
								if (text[i] === " " || text[i] === "\n") break;
							}
							if (triggerIndex >= 0 && triggerIndex < cursorCtx.cursor) {
								const path = [cursorCtx.blockIndex, cursorCtx.childIndex];
								editor.tf.delete({
									at: {
										anchor: { path, offset: triggerIndex },
										focus: { path, offset: cursorCtx.cursor },
									},
								});
							}
						}
					}

					editor.tf.insertNodes([mentionNode, { text: " " }] as unknown as TElement[], {
						select: true,
					});
				});
				editor.tf.focus();
			},
			[editor, getCurrentValue]
		);

		// Backwards-compatible shim — pre-folder callers pass a doc-only
		// payload; we route them through ``insertMentionChip`` with
		// ``kind: "doc"``.
		const insertDocumentChip = useCallback(
			(
				doc: Pick<Document, "id" | "title" | "document_type">,
				options?: { removeTriggerText?: boolean }
			) => {
				insertMentionChip({ ...doc, kind: "doc" }, options);
			},
			[insertMentionChip]
		);

		// Remove the chip(s) matching the given (id, document_type) pair.
		// Goes through ``tf.removeNodes`` so Slate keeps the surrounding
		// selection valid — the previous ``setValue``-based filter wiped
		// selection on every removal, which is why the caret vanished
		// when the X button was clicked. Iterates descending so removing
		// one entry doesn't invalidate the path of subsequent matches.
		// In practice chips are deduped by ``getMentionDocKey`` so this
		// loop runs at most once; the descending iteration is defense
		// against any future divergence.
		const removeDocumentChip = useCallback(
			(docId: number, docType?: string) => {
				const match = (n: unknown) => {
					if (!n || typeof n !== "object" || !("type" in n)) return false;
					const node = n as MentionElementNode;
					if (node.type !== MENTION_TYPE) return false;
					if (node.id !== docId) return false;
					return (node.document_type ?? "UNKNOWN") === (docType ?? "UNKNOWN");
				};

				const entries = Array.from(editor.api.nodes({ at: [], match })) as NodeEntry[];
				if (entries.length === 0) return;
				editor.tf.withoutNormalizing(() => {
					for (const [, path] of entries.reverse()) {
						editor.tf.removeNodes({ at: path });
					}
				});
			},
			[editor]
		);

		// Combined "remove chip end-to-end" used by both the Backspace
		// keybinding and the in-chip X button. Keeping these two surfaces
		// pinned to a single helper guarantees they can never diverge —
		// e.g. one path forgetting to notify the parent atom.
		const removeChip = useCallback(
			(docId: number, docType: string | undefined) => {
				removeDocumentChip(docId, docType);
				onDocumentRemove?.(docId, docType);
			},
			[onDocumentRemove, removeDocumentChip]
		);

		// Update the streaming status on a chip in place. ``tf.setNodes``
		// merges the partial props onto every node matching the
		// predicate without rebuilding the document, so the user's
		// selection stays put — important because status transitions
		// arrive as backend events while the user may be mid-typing.
		const setDocumentChipStatus = useCallback(
			(
				docId: number,
				docType: string | undefined,
				statusLabel: string | null,
				statusKind: MentionStatusKind = "pending"
			) => {
				const match = (n: unknown) => {
					if (!n || typeof n !== "object" || !("type" in n)) return false;
					const node = n as MentionElementNode;
					if (node.type !== MENTION_TYPE) return false;
					if (node.id !== docId) return false;
					return (node.document_type ?? "UNKNOWN") === (docType ?? "UNKNOWN");
				};

				editor.tf.setNodes(
					{
						statusLabel,
						statusKind: statusLabel ? statusKind : undefined,
					} as Partial<TElement>,
					{ at: [], match }
				);
			},
			[editor]
		);

		const clear = useCallback(() => {
			setValue(EMPTY_VALUE);
			// ``tf.setValue`` (inside ``setValue``) wipes the editor's
			// selection — without this, after the user presses Enter to
			// submit, the composer is left with no caret and they would
			// have to click before typing again.
			requestAnimationFrame(focusAtEnd);
		}, [focusAtEnd, setValue]);

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
				// If we already have a Plate selection (user was typing
				// before focus left), preserve it — just refocus. If we
				// don't (first mount, or focus was lost without a
				// surviving selection), seed a selection at end-of-doc
				// so the contentEditable shows a caret instead of an
				// invisible focus ring.
				focus: () => {
					try {
						if (!editor.selection) {
							editor.tf.select(editor.api.end([]));
						}
						editor.tf.focus();
					} catch {
						editableRef.current?.focus();
					}
				},
				clear,
				setText,
				getText,
				getMentionedDocuments: getMentionedDocs,
				insertMentionChip,
				insertDocumentChip,
				removeDocumentChip,
				setDocumentChipStatus,
			}),
			[
				clear,
				editor,
				getMentionedDocs,
				getText,
				insertMentionChip,
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
				removeChip(prev.id, prev.document_type);
			},
			[editor.selection, getCurrentValue, onKeyDown, onSubmit, removeChip]
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

		const mentionEditorContextValue = useMemo<MentionEditorContextValue>(
			() => ({ removeChip }),
			[removeChip]
		);

		return (
			<div className="relative w-full">
				<MentionEditorContext.Provider value={mentionEditorContextValue}>
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
				</MentionEditorContext.Provider>
			</div>
		);
	}
);

InlineMentionEditor.displayName = "InlineMentionEditor";
