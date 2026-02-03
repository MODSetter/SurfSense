"use client";

import { X } from "lucide-react";
import {
	createElement,
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useRef,
	useState,
} from "react";
import ReactDOMServer from "react-dom/server";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { Document } from "@/contracts/types/document.types";
import { cn } from "@/lib/utils";

export interface MentionedDocument {
	id: number;
	title: string;
	document_type?: string;
}

export interface InlineMentionEditorRef {
	focus: () => void;
	clear: () => void;
	getText: () => string;
	getMentionedDocuments: () => MentionedDocument[];
	insertDocumentChip: (doc: Pick<Document, "id" | "title" | "document_type">) => void;
}

interface InlineMentionEditorProps {
	placeholder?: string;
	onMentionTrigger?: (query: string) => void;
	onMentionClose?: () => void;
	onSubmit?: () => void;
	onChange?: (text: string, docs: MentionedDocument[]) => void;
	onDocumentRemove?: (docId: number, docType?: string) => void;
	onKeyDown?: (e: React.KeyboardEvent) => void;
	disabled?: boolean;
	className?: string;
	initialDocuments?: MentionedDocument[];
}

// Unique data attribute to identify chip elements
const CHIP_DATA_ATTR = "data-mention-chip";
const CHIP_ID_ATTR = "data-mention-id";
const CHIP_DOCTYPE_ATTR = "data-mention-doctype";

/**
 * Type guard to check if a node is a chip element
 */
function isChipElement(node: Node | null): node is HTMLSpanElement {
	return (
		node !== null &&
		node.nodeType === Node.ELEMENT_NODE &&
		(node as Element).hasAttribute(CHIP_DATA_ATTR)
	);
}

/**
 * Safely parse chip ID from element attribute
 */
function getChipId(element: Element): number | null {
	const idStr = element.getAttribute(CHIP_ID_ATTR);
	if (!idStr) return null;
	const id = parseInt(idStr, 10);
	return Number.isNaN(id) ? null : id;
}

/**
 * Get chip document type from element attribute
 */
function getChipDocType(element: Element): string {
	return element.getAttribute(CHIP_DOCTYPE_ATTR) ?? "UNKNOWN";
}

export const InlineMentionEditor = forwardRef<InlineMentionEditorRef, InlineMentionEditorProps>(
	(
		{
			placeholder = "Type @ to mention documents...",
			onMentionTrigger,
			onMentionClose,
			onSubmit,
			onChange,
			onDocumentRemove,
			onKeyDown,
			disabled = false,
			className,
			initialDocuments = [],
		},
		ref
	) => {
		const editorRef = useRef<HTMLDivElement>(null);
		const [isEmpty, setIsEmpty] = useState(true);
		const [mentionedDocs, setMentionedDocs] = useState<Map<string, MentionedDocument>>(
			() => new Map(initialDocuments.map((d) => [`${d.document_type ?? "UNKNOWN"}:${d.id}`, d]))
		);
		const isComposingRef = useRef(false);

		// Sync initial documents
		useEffect(() => {
			if (initialDocuments.length > 0) {
				setMentionedDocs(
					new Map(initialDocuments.map((d) => [`${d.document_type ?? "UNKNOWN"}:${d.id}`, d]))
				);
			}
		}, [initialDocuments]);

		// Focus at the end of the editor
		const focusAtEnd = useCallback(() => {
			if (!editorRef.current) return;
			editorRef.current.focus();
			const selection = window.getSelection();
			const range = document.createRange();
			range.selectNodeContents(editorRef.current);
			range.collapse(false);
			selection?.removeAllRanges();
			selection?.addRange(range);
		}, []);

		// Get plain text content (excluding chips)
		const getText = useCallback((): string => {
			if (!editorRef.current) return "";

			let text = "";
			const walker = document.createTreeWalker(
				editorRef.current,
				NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
				{
					acceptNode: (node) => {
						// Skip chip elements entirely
						if (node.nodeType === Node.ELEMENT_NODE) {
							const el = node as Element;
							if (el.hasAttribute(CHIP_DATA_ATTR)) {
								return NodeFilter.FILTER_REJECT; // Skip this subtree
							}
							return NodeFilter.FILTER_SKIP; // Continue into children
						}
						return NodeFilter.FILTER_ACCEPT;
					},
				}
			);

			let node: Node | null = walker.nextNode();
			while (node) {
				if (node.nodeType === Node.TEXT_NODE) {
					text += node.textContent;
				}
				node = walker.nextNode();
			}

			return text.trim();
		}, []);

		// Get all mentioned documents
		const getMentionedDocuments = useCallback((): MentionedDocument[] => {
			return Array.from(mentionedDocs.values());
		}, [mentionedDocs]);

		// Create a chip element for a document
		const createChipElement = useCallback(
			(doc: MentionedDocument): HTMLSpanElement => {
				const chip = document.createElement("span");
				chip.setAttribute(CHIP_DATA_ATTR, "true");
				chip.setAttribute(CHIP_ID_ATTR, String(doc.id));
				chip.setAttribute(CHIP_DOCTYPE_ATTR, doc.document_type ?? "UNKNOWN");
				chip.contentEditable = "false";
				chip.className =
					"inline-flex items-center gap-1 mx-0.5 pl-1 pr-0.5 py-0.5 rounded bg-primary/10 text-xs font-bold text-primary/60 select-none";
				chip.style.userSelect = "none";
				chip.style.verticalAlign = "baseline";

				// Add document type icon
				const iconSpan = document.createElement("span");
				iconSpan.className = "shrink-0 flex items-center text-muted-foreground";
				iconSpan.innerHTML = ReactDOMServer.renderToString(
					getConnectorIcon(doc.document_type ?? "UNKNOWN", "h-3 w-3")
				);

				const titleSpan = document.createElement("span");
				titleSpan.className = "max-w-[120px] truncate";
				titleSpan.textContent = doc.title;
				titleSpan.title = doc.title;

				const removeBtn = document.createElement("button");
				removeBtn.type = "button";
				removeBtn.className =
					"size-3 flex items-center justify-center rounded-full hover:bg-primary/20 transition-colors ml-0.5";
				removeBtn.innerHTML = ReactDOMServer.renderToString(
					createElement(X, { className: "h-2.5 w-2.5", strokeWidth: 2.5 })
				);
				removeBtn.onclick = (e) => {
					e.preventDefault();
					e.stopPropagation();
					chip.remove();
					const docKey = `${doc.document_type ?? "UNKNOWN"}:${doc.id}`;
					setMentionedDocs((prev) => {
						const next = new Map(prev);
						next.delete(docKey);
						return next;
					});
					// Notify parent that a document was removed
					onDocumentRemove?.(doc.id, doc.document_type);
					focusAtEnd();
				};

				chip.appendChild(iconSpan);
				chip.appendChild(titleSpan);
				chip.appendChild(removeBtn);

				return chip;
			},
			[focusAtEnd, onDocumentRemove]
		);

		// Insert a document chip at the current cursor position
		const insertDocumentChip = useCallback(
			(doc: Pick<Document, "id" | "title" | "document_type">) => {
				if (!editorRef.current) return;

				// Validate required fields for type safety
				if (typeof doc.id !== "number" || typeof doc.title !== "string") {
					console.warn("[InlineMentionEditor] Invalid document passed to insertDocumentChip:", doc);
					return;
				}

				const mentionDoc: MentionedDocument = {
					id: doc.id,
					title: doc.title,
					document_type: doc.document_type,
				};

				// Add to mentioned docs map using unique key
				const docKey = `${doc.document_type ?? "UNKNOWN"}:${doc.id}`;
				setMentionedDocs((prev) => new Map(prev).set(docKey, mentionDoc));

				// Find and remove the @query text
				const selection = window.getSelection();
				if (!selection || selection.rangeCount === 0) {
					// No selection, just append
					const chip = createChipElement(mentionDoc);
					editorRef.current.appendChild(chip);
					editorRef.current.appendChild(document.createTextNode(" "));
					focusAtEnd();
					return;
				}

				// Find the @ symbol before the cursor and remove it along with any query text
				const range = selection.getRangeAt(0);
				const textNode = range.startContainer;

				if (textNode.nodeType === Node.TEXT_NODE) {
					const text = textNode.textContent || "";
					const cursorPos = range.startOffset;

					// Find the @ symbol before cursor
					let atIndex = -1;
					for (let i = cursorPos - 1; i >= 0; i--) {
						if (text[i] === "@") {
							atIndex = i;
							break;
						}
					}

					if (atIndex !== -1) {
						// Remove @query and insert chip
						const beforeAt = text.slice(0, atIndex);
						const afterCursor = text.slice(cursorPos);

						// Create chip
						const chip = createChipElement(mentionDoc);

						// Replace text node content
						const parent = textNode.parentNode;
						if (parent) {
							const beforeNode = document.createTextNode(beforeAt);
							const afterNode = document.createTextNode(` ${afterCursor}`);

							parent.insertBefore(beforeNode, textNode);
							parent.insertBefore(chip, textNode);
							parent.insertBefore(afterNode, textNode);
							parent.removeChild(textNode);

							// Set cursor after the chip
							const newRange = document.createRange();
							newRange.setStart(afterNode, 1);
							newRange.collapse(true);
							selection.removeAllRanges();
							selection.addRange(newRange);
						}
					} else {
						// No @ found, just insert at cursor
						const chip = createChipElement(mentionDoc);
						range.insertNode(chip);
						range.setStartAfter(chip);
						range.collapse(true);

						// Add space after chip
						const space = document.createTextNode(" ");
						range.insertNode(space);
						range.setStartAfter(space);
						range.collapse(true);
					}
				} else {
					// Not in a text node, append to editor
					const chip = createChipElement(mentionDoc);
					editorRef.current.appendChild(chip);
					editorRef.current.appendChild(document.createTextNode(" "));
					focusAtEnd();
				}

				// Update empty state
				setIsEmpty(false);

				// Trigger onChange
				if (onChange) {
					setTimeout(() => {
						onChange(getText(), getMentionedDocuments());
					}, 0);
				}
			},
			[createChipElement, focusAtEnd, getText, getMentionedDocuments, onChange]
		);

		// Clear the editor
		const clear = useCallback(() => {
			if (editorRef.current) {
				editorRef.current.innerHTML = "";
				setIsEmpty(true);
				setMentionedDocs(new Map());
			}
		}, []);

		// Expose methods via ref
		useImperativeHandle(ref, () => ({
			focus: () => editorRef.current?.focus(),
			clear,
			getText,
			getMentionedDocuments,
			insertDocumentChip,
		}));

		// Handle input changes
		const handleInput = useCallback(() => {
			if (!editorRef.current) return;

			const text = getText();
			const empty = text.length === 0 && mentionedDocs.size === 0;
			setIsEmpty(empty);

			// Check for @ mentions
			const selection = window.getSelection();
			let shouldTriggerMention = false;
			let mentionQuery = "";

			if (selection && selection.rangeCount > 0) {
				const range = selection.getRangeAt(0);
				const textNode = range.startContainer;

				if (textNode.nodeType === Node.TEXT_NODE) {
					const textContent = textNode.textContent || "";
					const cursorPos = range.startOffset;

					// Look for @ before cursor
					let atIndex = -1;
					for (let i = cursorPos - 1; i >= 0; i--) {
						if (textContent[i] === "@") {
							atIndex = i;
							break;
						}
						// Stop if we hit a space (@ must be at word boundary)
						if (textContent[i] === " " || textContent[i] === "\n") {
							break;
						}
					}

					if (atIndex !== -1) {
						const query = textContent.slice(atIndex + 1, cursorPos);
						// Only trigger if query doesn't start with space
						if (!query.startsWith(" ")) {
							shouldTriggerMention = true;
							mentionQuery = query;
						}
					}
				}
			}

			// If no @ found before cursor, check if text contains @ at all
			// If text is empty or doesn't contain @, close the mention
			if (!shouldTriggerMention) {
				if (text.length === 0 || !text.includes("@")) {
					onMentionClose?.();
				} else {
					// Text contains @ but not before cursor, close mention
					onMentionClose?.();
				}
			} else {
				onMentionTrigger?.(mentionQuery);
			}

			// Notify parent of change
			onChange?.(text, Array.from(mentionedDocs.values()));
		}, [getText, mentionedDocs, onChange, onMentionTrigger, onMentionClose]);

		// Handle keydown
		const handleKeyDown = useCallback(
			(e: React.KeyboardEvent<HTMLDivElement>) => {
				// Let parent handle navigation keys when mention popover is open
				if (onKeyDown) {
					onKeyDown(e);
					if (e.defaultPrevented) return;
				}

				// Handle Enter for submit (without shift)
				if (e.key === "Enter" && !e.shiftKey) {
					e.preventDefault();
					onSubmit?.();
					return;
				}

				// Handle backspace on chips
				if (e.key === "Backspace") {
					const selection = window.getSelection();
					if (selection && selection.rangeCount > 0) {
						const range = selection.getRangeAt(0);
						if (range.collapsed) {
							// Check if cursor is right after a chip
							const node = range.startContainer;
							const offset = range.startOffset;

							if (node.nodeType === Node.TEXT_NODE && offset === 0) {
								// Check previous sibling using type guard
								const prevSibling = node.previousSibling;
								if (isChipElement(prevSibling)) {
									e.preventDefault();
									const chipId = getChipId(prevSibling);
									const chipDocType = getChipDocType(prevSibling);
									if (chipId !== null) {
										prevSibling.remove();
										const chipKey = `${chipDocType}:${chipId}`;
										setMentionedDocs((prev) => {
											const next = new Map(prev);
											next.delete(chipKey);
											return next;
										});
										// Notify parent that a document was removed
										onDocumentRemove?.(chipId, chipDocType);
									}
									return;
								}
								// Check if we're about to delete @ at the start
								const textContent = node.textContent || "";
								if (textContent.length > 0 && textContent[0] === "@") {
									// Will delete @, close mention popover
									setTimeout(() => {
										onMentionClose?.();
									}, 0);
								}
							} else if (node.nodeType === Node.TEXT_NODE && offset > 0) {
								// Check if we're about to delete @
								const textContent = node.textContent || "";
								if (textContent[offset - 1] === "@") {
									// Will delete @, close mention popover
									setTimeout(() => {
										onMentionClose?.();
									}, 0);
								}
							} else if (node.nodeType === Node.ELEMENT_NODE && offset > 0) {
								// Check if previous child is a chip using type guard
								const prevChild = (node as Element).childNodes[offset - 1];
								if (isChipElement(prevChild)) {
									e.preventDefault();
									const chipId = getChipId(prevChild);
									const chipDocType = getChipDocType(prevChild);
									if (chipId !== null) {
										prevChild.remove();
										const chipKey = `${chipDocType}:${chipId}`;
										setMentionedDocs((prev) => {
											const next = new Map(prev);
											next.delete(chipKey);
											return next;
										});
										// Notify parent that a document was removed
										onDocumentRemove?.(chipId, chipDocType);
									}
								}
							}
						}
					}
				}
			},
			[onKeyDown, onSubmit, onDocumentRemove, onMentionClose]
		);

		// Handle paste - strip formatting
		const handlePaste = useCallback((e: React.ClipboardEvent) => {
			e.preventDefault();
			const text = e.clipboardData.getData("text/plain");
			document.execCommand("insertText", false, text);
		}, []);

		// Handle composition (for IME input)
		const handleCompositionStart = useCallback(() => {
			isComposingRef.current = true;
		}, []);

		const handleCompositionEnd = useCallback(() => {
			isComposingRef.current = false;
			handleInput();
		}, [handleInput]);

		return (
			<div className="relative w-full">
				{/** biome-ignore lint/a11y/useSemanticElements: <not important> */}
				<div
					ref={editorRef}
					contentEditable={!disabled}
					suppressContentEditableWarning
					tabIndex={disabled ? -1 : 0}
					onInput={handleInput}
					onKeyDown={handleKeyDown}
					onPaste={handlePaste}
					onCompositionStart={handleCompositionStart}
					onCompositionEnd={handleCompositionEnd}
					className={cn(
						"min-h-[24px] max-h-32 overflow-y-auto",
						"text-sm outline-none",
						"whitespace-pre-wrap break-words",
						disabled && "opacity-50 cursor-not-allowed",
						className
					)}
					style={{ wordBreak: "break-word" }}
					data-placeholder={placeholder}
					aria-label="Message input with inline mentions"
					role="textbox"
					aria-multiline="true"
				/>
				{/* Placeholder with fade animation on change */}
				{isEmpty && (
					<div
						key={placeholder}
						className="absolute top-0 left-0 pointer-events-none text-muted-foreground text-sm animate-in fade-in duration-1000"
						aria-hidden="true"
					>
						{placeholder}
					</div>
				)}
			</div>
		);
	}
);

InlineMentionEditor.displayName = "InlineMentionEditor";
