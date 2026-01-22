"use client";

import { Send, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { MemberMentionPicker } from "../member-mention-picker/member-mention-picker";
import type { MemberOption } from "../member-mention-picker/types";
import type { CommentComposerProps, InsertedMention, MentionState } from "./types";

function convertDisplayToData(displayContent: string, mentions: InsertedMention[]): string {
	let result = displayContent;

	const sortedMentions = [...mentions].sort((a, b) => b.displayName.length - a.displayName.length);

	for (const mention of sortedMentions) {
		const displayPattern = new RegExp(
			`@${escapeRegExp(mention.displayName)}(?=\\s|$|[.,!?;:])`,
			"g"
		);
		const dataFormat = `@[${mention.id}]`;
		result = result.replace(displayPattern, dataFormat);
	}

	return result;
}

function escapeRegExp(string: string): string {
	return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findMentionTrigger(
	text: string,
	cursorPos: number,
	insertedMentions: InsertedMention[]
): { isActive: boolean; query: string; startIndex: number } {
	const textBeforeCursor = text.slice(0, cursorPos);

	const mentionMatch = textBeforeCursor.match(/(?:^|[\s])@([^\s]*)$/);

	if (!mentionMatch) {
		return { isActive: false, query: "", startIndex: 0 };
	}

	const query = mentionMatch[1];
	const atIndex = cursorPos - query.length - 1;

	if (atIndex > 0) {
		const charBefore = text[atIndex - 1];
		if (charBefore && !/[\s]/.test(charBefore)) {
			return { isActive: false, query: "", startIndex: 0 };
		}
	}

	const textFromAt = text.slice(atIndex);

	for (const mention of insertedMentions) {
		const mentionPattern = `@${mention.displayName}`;

		if (textFromAt.startsWith(mentionPattern)) {
			const charAfterMention = text[atIndex + mentionPattern.length];
			if (!charAfterMention || /[\s.,!?;:]/.test(charAfterMention)) {
				if (cursorPos <= atIndex + mentionPattern.length) {
					return { isActive: false, query: "", startIndex: 0 };
				}
			}
		}
	}

	if (query.length > 50) {
		return { isActive: false, query: "", startIndex: 0 };
	}

	return { isActive: true, query, startIndex: atIndex };
}

export function CommentComposer({
	members,
	membersLoading = false,
	placeholder = "Comment or @mention",
	submitLabel = "Send",
	isSubmitting = false,
	onSubmit,
	onCancel,
	autoFocus = false,
	initialValue = "",
}: CommentComposerProps) {
	const [displayContent, setDisplayContent] = useState(initialValue);
	const [insertedMentions, setInsertedMentions] = useState<InsertedMention[]>([]);
	const [mentionsInitialized, setMentionsInitialized] = useState(false);
	const [mentionState, setMentionState] = useState<MentionState>({
		isActive: false,
		query: "",
		startIndex: 0,
	});
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	const filteredMembers = mentionState.query
		? members.filter(
				(member) =>
					member.displayName?.toLowerCase().includes(mentionState.query.toLowerCase()) ||
					member.email.toLowerCase().includes(mentionState.query.toLowerCase())
			)
		: members;

	const closeMentionPicker = useCallback(() => {
		setMentionState({ isActive: false, query: "", startIndex: 0 });
		setHighlightedIndex(0);
	}, []);

	const insertMention = useCallback(
		(member: MemberOption) => {
			const displayName = member.displayName || member.email.split("@")[0];
			const before = displayContent.slice(0, mentionState.startIndex);
			const cursorPos = textareaRef.current?.selectionStart ?? displayContent.length;
			const after = displayContent.slice(cursorPos);
			const mentionText = `@${displayName} `;
			const newContent = before + mentionText + after;

			setDisplayContent(newContent);
			setInsertedMentions((prev) => {
				const exists = prev.some((m) => m.id === member.id && m.displayName === displayName);
				if (exists) return prev;
				return [...prev, { id: member.id, displayName }];
			});
			closeMentionPicker();

			requestAnimationFrame(() => {
				if (textareaRef.current) {
					const cursorPos = before.length + mentionText.length;
					textareaRef.current.focus();
					textareaRef.current.setSelectionRange(cursorPos, cursorPos);
				}
			});
		},
		[displayContent, mentionState.startIndex, closeMentionPicker]
	);

	const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
		const value = e.target.value;
		const cursorPos = e.target.selectionStart;
		setDisplayContent(value);

		// Auto-resize textarea on content change
		requestAnimationFrame(() => {
			const textarea = e.target;
			textarea.style.height = "auto";
			textarea.style.height = `${textarea.scrollHeight}px`;
		});

		const triggerResult = findMentionTrigger(value, cursorPos, insertedMentions);

		if (triggerResult.isActive) {
			setMentionState(triggerResult);
			setHighlightedIndex(0);
		} else if (mentionState.isActive) {
			closeMentionPicker();
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (!mentionState.isActive) {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				handleSubmit();
			}
			return;
		}

		switch (e.key) {
			case "ArrowDown":
			case "Tab":
				if (!e.shiftKey) {
					e.preventDefault();
					setHighlightedIndex((prev) => (prev < filteredMembers.length - 1 ? prev + 1 : 0));
				} else if (e.key === "Tab") {
					e.preventDefault();
					setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : filteredMembers.length - 1));
				}
				break;
			case "ArrowUp":
				e.preventDefault();
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : filteredMembers.length - 1));
				break;
			case "Enter":
				e.preventDefault();
				if (filteredMembers[highlightedIndex]) {
					insertMention(filteredMembers[highlightedIndex]);
				}
				break;
			case "Escape":
				e.preventDefault();
				closeMentionPicker();
				break;
		}
	};

	const handleSubmit = () => {
		const trimmed = displayContent.trim();
		if (!trimmed || isSubmitting) return;

		const dataContent = convertDisplayToData(trimmed, insertedMentions);
		onSubmit(dataContent);
		setDisplayContent("");
		setInsertedMentions([]);
	};

	// Pre-populate insertedMentions from initialValue when members are loaded
	useEffect(() => {
		if (mentionsInitialized || !initialValue || members.length === 0) return;

		const mentionPattern = /@([^\s@]+(?:\s+[^\s@]+)*?)(?=\s|$|[.,!?;:]|@)/g;
		const foundMentions: InsertedMention[] = [];
		const matches = initialValue.matchAll(mentionPattern);

		for (const match of matches) {
			const displayName = match[1];
			const member = members.find(
				(m) => m.displayName === displayName || m.email.split("@")[0] === displayName
			);
			if (member) {
				const exists = foundMentions.some((m) => m.id === member.id);
				if (!exists) {
					foundMentions.push({ id: member.id, displayName });
				}
			}
		}

		if (foundMentions.length > 0) {
			setInsertedMentions(foundMentions);
		}
		setMentionsInitialized(true);
	}, [initialValue, members, mentionsInitialized]);

	useEffect(() => {
		if (autoFocus && textareaRef.current) {
			textareaRef.current.focus();
		}
	}, [autoFocus]);

	const canSubmit = displayContent.trim().length > 0 && !isSubmitting;

	// Auto-resize textarea
	const adjustTextareaHeight = useCallback(() => {
		const textarea = textareaRef.current;
		if (textarea) {
			textarea.style.height = "auto";
			textarea.style.height = `${textarea.scrollHeight}px`;
		}
	}, []);

	useEffect(() => {
		adjustTextareaHeight();
	}, [adjustTextareaHeight]);

	return (
		<div className="flex flex-col gap-2">
			<Popover
				open={mentionState.isActive}
				onOpenChange={(open) => !open && closeMentionPicker()}
				modal={false}
			>
				<PopoverAnchor asChild>
					<Textarea
						ref={textareaRef}
						value={displayContent}
						onChange={handleInputChange}
						onKeyDown={handleKeyDown}
						placeholder={placeholder}
						className="min-h-[40px] max-h-[200px] resize-none overflow-y-auto scrollbar-thin"
						rows={1}
						disabled={isSubmitting}
					/>
				</PopoverAnchor>
				<PopoverContent
					side="top"
					align="start"
					sideOffset={4}
					collisionPadding={8}
					className="w-72 p-0"
					onOpenAutoFocus={(e) => e.preventDefault()}
				>
					<MemberMentionPicker
						members={members}
						query={mentionState.query}
						highlightedIndex={highlightedIndex}
						isLoading={membersLoading}
						onSelect={insertMention}
						onHighlightChange={setHighlightedIndex}
					/>
				</PopoverContent>
			</Popover>

			<div className="flex items-center justify-end gap-2">
				{onCancel && (
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={onCancel}
						disabled={isSubmitting}
					>
						<X className="mr-1 size-4" />
						Cancel
					</Button>
				)}
				<Button
					type="button"
					size="sm"
					onClick={handleSubmit}
					disabled={!canSubmit}
					className={cn(!canSubmit && "opacity-50")}
				>
					<Send className="mr-1 size-4" />
					{submitLabel}
				</Button>
			</div>
		</div>
	);
}
