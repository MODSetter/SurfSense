"use client";

import { TagInput, type Tag as TagType } from "emblor";
import { useCallback, useEffect, useRef, useState } from "react";

function parseEmailsToTags(value: string): TagType[] {
	if (!value.trim()) return [];
	return value
		.split(",")
		.map((s) => s.trim())
		.filter(Boolean)
		.map((email, i) => ({ id: `${Date.now()}-${i}`, text: email }));
}

function tagsToEmailString(tags: TagType[]): string {
	return tags.map((t) => t.text).join(", ");
}

/**
 * Comma-separated email field rendered as a tag input. Internal tag
 * state is the source of truth; comma-string is propagated to the
 * caller via ``onChange`` whenever tags change (skipping the initial
 * mount to avoid spurious updates).
 */
export function EmailsTagField({
	id,
	value,
	onChange,
	placeholder,
}: {
	id: string;
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
}) {
	const [tags, setTags] = useState<TagType[]>(() => parseEmailsToTags(value));
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
	const isInitialMount = useRef(true);
	const onChangeRef = useRef(onChange);
	onChangeRef.current = onChange;

	useEffect(() => {
		if (isInitialMount.current) {
			isInitialMount.current = false;
			return;
		}
		onChangeRef.current(tagsToEmailString(tags));
	}, [tags]);

	const handleSetTags = useCallback((newTags: TagType[] | ((prev: TagType[]) => TagType[])) => {
		setTags((prev) => (typeof newTags === "function" ? newTags(prev) : newTags));
	}, []);

	const handleAddTag = useCallback((text: string) => {
		const trimmed = text.trim();
		if (!trimmed) return;
		setTags((prev) => {
			if (prev.some((tag) => tag.text === trimmed)) return prev;
			const newTag: TagType = { id: Date.now().toString(), text: trimmed };
			return [...prev, newTag];
		});
	}, []);

	return (
		<TagInput
			id={id}
			tags={tags}
			setTags={handleSetTags}
			placeholder={placeholder ?? "Add email"}
			onAddTag={handleAddTag}
			styleClasses={{
				inlineTagsContainer:
					"border border-input rounded-md bg-transparent shadow-xs transition-[color,box-shadow] outline-none focus-within:border-ring p-1 gap-1",
				input:
					"w-full min-w-[80px] focus-visible:outline-none shadow-none px-2 h-7 text-foreground placeholder:text-muted-foreground bg-transparent text-sm md:text-sm",
				tag: {
					body: "h-7 relative bg-accent dark:bg-muted/60 border-0 hover:bg-accent/80 dark:hover:bg-muted rounded-md font-medium text-xs text-foreground/80 ps-2 pe-7 flex",
					closeButton:
						"absolute -inset-y-px -end-px p-0 rounded-e-md flex size-7 transition-colors outline-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring/70 text-foreground hover:text-foreground",
				},
			}}
			activeTagIndex={activeTagIndex}
			setActiveTagIndex={setActiveTagIndex}
		/>
	);
}
