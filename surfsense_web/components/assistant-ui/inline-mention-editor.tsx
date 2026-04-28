"use client";

import { X } from "lucide-react";
import type { ReactElement } from "react";
import {
	createElement,
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useRef,
	useState,
} from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { Document } from "@/contracts/types/document.types";
import { cn } from "@/lib/utils";

// Render a React element to an HTML string on the client without pulling
// `react-dom/server` into the bundle. `createRoot` + `flushSync` use the
// same `react-dom` package React itself imports, so this adds zero new
// runtime weight.
function renderElementToHTML(element: ReactElement): string {
	const container = document.createElement("div");
	const root = createRoot(container);
	flushSync(() => {
		root.render(element);
	});
	const html = container.innerHTML;
	root.unmount();
	return html;
}

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
	initialDocuments?: MentionedDocument[];
	initialText?: string;
}

// Unique data attribute to identify chip elements
const CHIP_DATA_ATTR = "data-mention-chip";
const CHIP_ID_ATTR = "data-mention-id";
const CHIP_DOCTYPE_ATTR = "data-mention-doctype";
const CHIP_STATUS_ATTR = "data-mention-status";

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
			onActionTrigger,
			onActionClose,
			onSubmit,
			onChange,
			onDocumentRemove,
			onKeyDown,
			disabled = false,
			className,
			initialDocuments = [],
			initialText,
		},
		ref
	) => {
		const editorRef = useRef<HTMLDivElement>(null);
		const [isEmpty, setIsEmpty] = useState(true);
		const [mentionedDocs, setMentionedDocs] = useState<Map<string, MentionedDocument>>(
			() => new Map(initialDocuments.map((d) => [`${d.document_type ?? "UNKNOWN"}:${d.id}`, d]))
		);
		const isComposingRef = useRef(false);
		const lastSelectionRangeRef = useRef<Range | null>(null);
		const isSelectionInsideEditor = useCallback(
			(selection: Selection | null): selection is Selection => {
				if (!selection || selection.rangeCount === 0 || !editorRef.current) return false;
				const range = selection.getRangeAt(0);
				return editorRef.current.contains(range.startContainer);
			},
			[]
		);

		const rememberSelection = useCallback(() => {
			const selection = window.getSelection();
			if (!isSelectionInsideEditor(selection)) return;
			lastSelectionRangeRef.current = selection.getRangeAt(0).cloneRange();
		}, [isSelectionInsideEditor]);

		const restoreRememberedSelection = useCallback((): Selection | null => {
			const selection = window.getSelection();
			if (!selection) return null;
			if (!lastSelectionRangeRef.current) return selection;
			selection.removeAllRanges();
			selection.addRange(lastSelectionRangeRef.current.cloneRange());
			return selection;
		}, []);

		useEffect(() => {
			const handleSelectionChange = () => {
				if (document.activeElement !== editorRef.current) return;
				rememberSelection();
			};
			document.addEventListener("selectionchange", handleSelectionChange);
			return () => document.removeEventListener("selectionchange", handleSelectionChange);
		}, [rememberSelection]);


		// Sync initial documents
		useEffect(() => {
			if (initialDocuments.length > 0) {
				setMentionedDocs(
					new Map(initialDocuments.map((d) => [`${d.document_type ?? "UNKNOWN"}:${d.id}`, d]))
				);
			}
		}, [initialDocuments]);

		useEffect(() => {
			if (!initialText || !editorRef.current) return;
			editorRef.current.innerText = initialText;
			editorRef.current.appendChild(document.createElement("br"));
			editorRef.current.appendChild(document.createElement("br"));
			setIsEmpty(false);
			onChange?.(initialText, Array.from(mentionedDocs.values()));
			editorRef.current.focus();
			const sel = window.getSelection();
			const range = document.createRange();
			range.selectNodeContents(editorRef.current);
			range.collapse(false);
			sel?.removeAllRanges();
			sel?.addRange(range);
			const anchor = document.createElement("span");
			range.insertNode(anchor);
			anchor.scrollIntoView({ block: "end" });
			anchor.remove();
		}, [initialText]);

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

		// Get plain text content with inline mention tokens for chips.
		// This preserves the original query structure sent to the backend/LLM.
		const getText = useCallback((): string => {
			if (!editorRef.current) return "";

			const extractText = (node: Node): string => {
				if (node.nodeType === Node.TEXT_NODE) {
					return node.textContent ?? "";
				}

				if (node.nodeType === Node.ELEMENT_NODE) {
					const element = node as Element;

					// Preserve mention chips as inline @title tokens.
					if (element.hasAttribute(CHIP_DATA_ATTR)) {
						const title = element.querySelector("[data-mention-title='true']")?.textContent?.trim();
						if (title) {
							return `@${title}`;
						}
						return "";
					}

					let result = "";
					for (const child of Array.from(element.childNodes)) {
						result += extractText(child);
					}
					return result;
				}

				return "";
			};

			return extractText(editorRef.current).trim();
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
					"inline-flex items-center gap-1 mx-0.5 px-1 py-0.5 rounded bg-primary/10 text-xs font-bold text-primary/60 select-none cursor-default";
				chip.style.userSelect = "none";
				chip.style.verticalAlign = "baseline";

				// Container that swaps between icon and remove button on hover
				const iconContainer = document.createElement("span");
				iconContainer.className = "shrink-0 flex items-center size-3 relative";

				const iconSpan = document.createElement("span");
				iconSpan.className = "flex items-center text-muted-foreground";
				iconSpan.innerHTML = renderElementToHTML(
					getConnectorIcon(doc.document_type ?? "UNKNOWN", "h-3 w-3")
				);

				const removeBtn = document.createElement("button");
				removeBtn.type = "button";
				removeBtn.className =
					"size-3 items-center justify-center rounded-full text-muted-foreground transition-colors";
				removeBtn.style.display = "none";
				removeBtn.innerHTML = renderElementToHTML(
					createElement(X, { className: "h-3 w-3", strokeWidth: 2.5 })
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
					onDocumentRemove?.(doc.id, doc.document_type);
					focusAtEnd();
				};

				const titleSpan = document.createElement("span");
				titleSpan.className = "max-w-[120px] truncate";
				titleSpan.textContent = doc.title;
				titleSpan.title = doc.title;
				titleSpan.setAttribute("data-mention-title", "true");

				const statusSpan = document.createElement("span");
				statusSpan.setAttribute(CHIP_STATUS_ATTR, "true");
				statusSpan.className = "text-[10px] font-semibold opacity-80 hidden";

				const isTouchDevice = window.matchMedia("(hover: none)").matches;
				if (isTouchDevice) {
					// Mobile: icon on left, title, X on right
					chip.appendChild(iconSpan);
					chip.appendChild(titleSpan);
					chip.appendChild(statusSpan);
					removeBtn.style.display = "flex";
					removeBtn.className += " ml-0.5";
					chip.appendChild(removeBtn);
				} else {
					// Desktop: icon/X swap on hover in the same slot
					iconContainer.appendChild(iconSpan);
					iconContainer.appendChild(removeBtn);
					chip.addEventListener("mouseenter", () => {
						iconSpan.style.display = "none";
						removeBtn.style.display = "flex";
					});
					chip.addEventListener("mouseleave", () => {
						iconSpan.style.display = "";
						removeBtn.style.display = "none";
					});
					chip.appendChild(iconContainer);
					chip.appendChild(titleSpan);
					chip.appendChild(statusSpan);
				}

				return chip;
			},
			[focusAtEnd, onDocumentRemove]
		);

		// Insert a document chip at the current cursor position
		const insertDocumentChip = useCallback(
			(
				doc: Pick<Document, "id" | "title" | "document_type">,
				options?: { removeTriggerText?: boolean }
			) => {
				if (!editorRef.current) return;
				const removeTriggerText = options?.removeTriggerText ?? true;

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
				const hasActiveSelection = isSelectionInsideEditor(selection);
				const resolvedSelection = hasActiveSelection ? selection : restoreRememberedSelection();
				if (!resolvedSelection || resolvedSelection.rangeCount === 0) {
					// No selection, just append
					const chip = createChipElement(mentionDoc);
					editorRef.current.appendChild(chip);
					editorRef.current.appendChild(document.createTextNode(" "));
					focusAtEnd();
					rememberSelection();
					return;
				}

				// Find the @ symbol before the cursor and remove it along with any query text
				const range = resolvedSelection.getRangeAt(0);
				const textNode = range.startContainer;

				if (textNode.nodeType === Node.TEXT_NODE && removeTriggerText) {
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
							resolvedSelection.removeAllRanges();
							resolvedSelection.addRange(newRange);
							rememberSelection();
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
						resolvedSelection.removeAllRanges();
						resolvedSelection.addRange(range);
						rememberSelection();
					}
				} else {
					// Either explicit non-trigger insertion or no @query present.
					const chip = createChipElement(mentionDoc);
					range.insertNode(chip);
					range.setStartAfter(chip);
					range.collapse(true);
					const space = document.createTextNode(" ");
					range.insertNode(space);
					range.setStartAfter(space);
					range.collapse(true);
					resolvedSelection.removeAllRanges();
					resolvedSelection.addRange(range);
					rememberSelection();
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
			[
				createChipElement,
				focusAtEnd,
				getText,
				getMentionedDocuments,
				isSelectionInsideEditor,
				onChange,
				rememberSelection,
				restoreRememberedSelection,
			]
		);

		// Clear the editor
		const clear = useCallback(() => {
			if (editorRef.current) {
				editorRef.current.innerHTML = "";
				setIsEmpty(true);
				setMentionedDocs(new Map());
			}
		}, []);

		// Replace editor content with plain text and place cursor at end
		const setText = useCallback(
			(text: string) => {
				if (!editorRef.current) return;
				editorRef.current.innerText = text;
				const empty = text.length === 0;
				setIsEmpty(empty);
				onChange?.(text, Array.from(mentionedDocs.values()));
				focusAtEnd();
			},
			[focusAtEnd, onChange, mentionedDocs]
		);

		const setDocumentChipStatus = useCallback(
			(
				docId: number,
				docType: string | undefined,
				statusLabel: string | null,
				statusKind: "pending" | "processing" | "ready" | "failed" = "pending"
			) => {
				if (!editorRef.current) return;

				const chips = editorRef.current.querySelectorAll<HTMLSpanElement>(
					`span[${CHIP_DATA_ATTR}="true"]`
				);
				for (const chip of chips) {
					const chipId = getChipId(chip);
					const chipType = getChipDocType(chip);
					if (chipId !== docId) continue;
					if ((docType ?? "UNKNOWN") !== chipType) continue;

					const statusEl = chip.querySelector<HTMLSpanElement>(`span[${CHIP_STATUS_ATTR}="true"]`);
					if (!statusEl) continue;

					if (!statusLabel) {
						statusEl.textContent = "";
						statusEl.className = "text-[10px] font-semibold opacity-80 hidden";
						continue;
					}

					const statusClass =
						statusKind === "failed"
							? "text-destructive"
							: statusKind === "processing"
								? "text-amber-700"
								: statusKind === "ready"
									? "text-emerald-700"
									: "text-amber-700";
					statusEl.textContent = statusLabel;
					statusEl.className = `text-[10px] font-semibold opacity-80 ${statusClass}`;
				}
			},
			[]
		);

		const removeDocumentChip = useCallback(
			(docId: number, docType?: string) => {
				if (!editorRef.current) return;
				const chipKey = `${docType ?? "UNKNOWN"}:${docId}`;
				const chips = editorRef.current.querySelectorAll<HTMLSpanElement>(
					`span[${CHIP_DATA_ATTR}="true"]`
				);
				for (const chip of chips) {
					if (getChipId(chip) === docId && getChipDocType(chip) === (docType ?? "UNKNOWN")) {
						chip.remove();
						break;
					}
				}
				setMentionedDocs((prev) => {
					const next = new Map(prev);
					next.delete(chipKey);
					return next;
				});

				const text = getText();
				const empty = text.length === 0 && mentionedDocs.size <= 1;
				setIsEmpty(empty);
			},
			[getText, mentionedDocs.size]
		);

		// Expose methods via ref
		useImperativeHandle(ref, () => ({
			focus: () => editorRef.current?.focus(),
			clear,
			setText,
			getText,
			getMentionedDocuments,
			insertDocumentChip,
			removeDocumentChip,
			setDocumentChipStatus,
		}));

		// Handle input changes
		const handleInput = useCallback(() => {
			if (!editorRef.current) return;

			const text = getText();
			const empty = text.length === 0 && mentionedDocs.size === 0;
			setIsEmpty(empty);

			// Unified trigger scan: find the leftmost @ or / in the current word.
			// Whichever trigger was typed first owns the token — the other character
			// is treated as part of the query, not as a separate trigger.
			const selection = window.getSelection();
			let shouldTriggerMention = false;
			let mentionQuery = "";
			let shouldTriggerAction = false;
			let actionQuery = "";

			if (selection && selection.rangeCount > 0) {
				const range = selection.getRangeAt(0);
				const textNode = range.startContainer;

				if (textNode.nodeType === Node.TEXT_NODE) {
					const textContent = textNode.textContent || "";
					const cursorPos = range.startOffset;

					let wordStart = 0;
					for (let i = cursorPos - 1; i >= 0; i--) {
						if (textContent[i] === " " || textContent[i] === "\n") {
							wordStart = i + 1;
							break;
						}
					}

					let triggerChar: "@" | "/" | null = null;
					let triggerIndex = -1;
					for (let i = wordStart; i < cursorPos; i++) {
						if (textContent[i] === "@" || textContent[i] === "/") {
							triggerChar = textContent[i] as "@" | "/";
							triggerIndex = i;
							break;
						}
					}

					if (triggerChar === "@" && triggerIndex !== -1) {
						const query = textContent.slice(triggerIndex + 1, cursorPos);
						if (!query.startsWith(" ")) {
							shouldTriggerMention = true;
							mentionQuery = query;
						}
					} else if (triggerChar === "/" && triggerIndex !== -1) {
						if (
							triggerIndex === 0 ||
							textContent[triggerIndex - 1] === " " ||
							textContent[triggerIndex - 1] === "\n"
						) {
							const query = textContent.slice(triggerIndex + 1, cursorPos);
							if (!query.startsWith(" ")) {
								shouldTriggerAction = true;
								actionQuery = query;
							}
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

			if (!shouldTriggerAction) {
				onActionClose?.();
			} else {
				onActionTrigger?.(actionQuery);
			}

			// Notify parent of change
			onChange?.(text, Array.from(mentionedDocs.values()));
			rememberSelection();
		}, [
			getText,
			mentionedDocs,
			onChange,
			onMentionTrigger,
			onMentionClose,
			onActionTrigger,
			onActionClose,
			rememberSelection,
		]);

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
					onKeyUp={rememberSelection}
					onMouseUp={rememberSelection}
					onBlur={rememberSelection}
					className={cn(
						"min-h-[24px] max-h-32 overflow-y-auto",
						"text-sm outline-none",
						"whitespace-pre-wrap wrap-break-word",
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
