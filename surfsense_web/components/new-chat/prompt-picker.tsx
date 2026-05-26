"use client";

import { useAtomValue } from "jotai";
import { Plus, WandSparkles } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import {
	forwardRef,
	useCallback,
	useDeferredValue,
	useEffect,
	useImperativeHandle,
	useMemo,
	useRef,
	useState,
} from "react";

import { promptsAtom } from "@/atoms/prompts/prompts-query.atoms";
import {
	ComposerSuggestionGroup,
	ComposerSuggestionGroupHeading,
	ComposerSuggestionItem,
	ComposerSuggestionList,
	ComposerSuggestionMessage,
	ComposerSuggestionSeparator,
	ComposerSuggestionSkeleton,
} from "@/components/new-chat/composer-suggestion-popup";

export interface PromptPickerRef {
	selectHighlighted: () => void;
	moveUp: () => void;
	moveDown: () => void;
}

interface PromptPickerProps {
	onSelect: (action: { name: string; prompt: string; mode: "transform" | "explore" }) => void;
	onDone: () => void;
	externalSearch?: string;
}

export const PromptPicker = forwardRef<PromptPickerRef, PromptPickerProps>(function PromptPicker(
	{ onSelect, onDone, externalSearch = "" },
	ref
) {
	const router = useRouter();
	const params = useParams();
	const { data: prompts, isLoading, isError } = useAtomValue(promptsAtom);
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const shouldScrollRef = useRef(false);
	const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

	// Defer the search value so filtering is non-urgent and the input stays responsive
	const deferredSearch = useDeferredValue(externalSearch);

	const filtered = useMemo(() => {
		const list = prompts ?? [];
		if (!deferredSearch) return list;
		return list.filter((a) => a.name.toLowerCase().includes(deferredSearch.toLowerCase()));
	}, [prompts, deferredSearch]);

	// Reset highlight when the deferred (filtered) search changes
	const prevSearchRef = useRef(deferredSearch);
	if (prevSearchRef.current !== deferredSearch) {
		prevSearchRef.current = deferredSearch;
		if (highlightedIndex !== 0) {
			setHighlightedIndex(0);
		}
	}

	const createPromptIndex = filtered.length;
	const totalItems = filtered.length + 1;
	const searchSpaceId = Array.isArray(params?.search_space_id)
		? params.search_space_id[0]
		: params?.search_space_id;

	const handleSelect = useCallback(
		(index: number) => {
			if (index === createPromptIndex) {
				onDone();
				if (searchSpaceId) {
					router.push(`/dashboard/${searchSpaceId}/user-settings/prompts`);
				}
				return;
			}
			const action = filtered[index];
			if (!action) return;
			onSelect({ name: action.name, prompt: action.prompt, mode: action.mode });
		},
		[filtered, onSelect, createPromptIndex, onDone, router, searchSpaceId]
	);

	useEffect(() => {
		if (!shouldScrollRef.current) return;
		shouldScrollRef.current = false;

		const rafId = requestAnimationFrame(() => {
			const item = itemRefs.current.get(highlightedIndex);
			const container = scrollContainerRef.current;
			if (item && container) {
				const itemRect = item.getBoundingClientRect();
				const containerRect = container.getBoundingClientRect();
				if (itemRect.top < containerRect.top || itemRect.bottom > containerRect.bottom) {
					item.scrollIntoView({ block: "nearest" });
				}
			}
		});

		return () => cancelAnimationFrame(rafId);
	}, [highlightedIndex]);

	useImperativeHandle(
		ref,
		() => ({
			selectHighlighted: () => handleSelect(highlightedIndex),
			moveUp: () => {
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : totalItems - 1));
			},
			moveDown: () => {
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev < totalItems - 1 ? prev + 1 : 0));
			},
		}),
		[totalItems, highlightedIndex, handleSelect]
	);

	return (
		<ComposerSuggestionList ref={scrollContainerRef}>
			{isLoading ? (
				<ComposerSuggestionSkeleton rows={8} mobileRows={8} />
			) : isError ? (
				<ComposerSuggestionMessage variant="destructive">Failed to load prompts</ComposerSuggestionMessage>
			) : filtered.length === 0 ? (
				<ComposerSuggestionMessage>No matching prompts</ComposerSuggestionMessage>
			) : (
				<ComposerSuggestionGroup>
					<ComposerSuggestionGroupHeading>Saved Prompts</ComposerSuggestionGroupHeading>
					{filtered.map((action, index) => (
						<ComposerSuggestionItem
							key={action.id}
							ref={(el) => {
								if (el) itemRefs.current.set(index, el);
								else itemRefs.current.delete(index);
							}}
							icon={<WandSparkles className="size-3.5" />}
							selected={index === highlightedIndex}
							onClick={() => handleSelect(index)}
							onMouseEnter={() => setHighlightedIndex(index)}
						>
							<span className="flex-1 truncate text-xs">{action.name}</span>
						</ComposerSuggestionItem>
					))}

					<ComposerSuggestionSeparator />
					<ComposerSuggestionItem
						ref={(el) => {
							if (el) itemRefs.current.set(createPromptIndex, el);
							else itemRefs.current.delete(createPromptIndex);
						}}
						icon={<Plus className="size-3.5" />}
						muted
						selected={highlightedIndex === createPromptIndex}
						onClick={() => handleSelect(createPromptIndex)}
						onMouseEnter={() => setHighlightedIndex(createPromptIndex)}
					>
						<span>Create prompt</span>
					</ComposerSuggestionItem>
				</ComposerSuggestionGroup>
			)}
		</ComposerSuggestionList>
	);
});
