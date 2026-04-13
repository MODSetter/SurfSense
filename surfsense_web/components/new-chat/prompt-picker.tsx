"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Plus, Zap } from "lucide-react";
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
import { userSettingsDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface PromptPickerRef {
	selectHighlighted: () => void;
	moveUp: () => void;
	moveDown: () => void;
}

interface PromptPickerProps {
	onSelect: (action: { name: string; prompt: string; mode: "transform" | "explore" }) => void;
	onDone: () => void;
	externalSearch?: string;
	containerStyle?: React.CSSProperties;
}

export const PromptPicker = forwardRef<PromptPickerRef, PromptPickerProps>(function PromptPicker(
	{ onSelect, onDone, externalSearch = "", containerStyle },
	ref
) {
	const setUserSettingsDialog = useSetAtom(userSettingsDialogAtom);
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

	const handleSelect = useCallback(
		(index: number) => {
			if (index === createPromptIndex) {
				onDone();
				setUserSettingsDialog({ open: true, initialTab: "prompts" });
				return;
			}
			const action = filtered[index];
			if (!action) return;
			onSelect({ name: action.name, prompt: action.prompt, mode: action.mode });
		},
		[filtered, onSelect, createPromptIndex, onDone, setUserSettingsDialog]
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
		<div
			className="fixed shadow-2xl rounded-lg border border-border dark:border-white/5 overflow-hidden bg-popover dark:bg-neutral-900 flex flex-col w-[280px] sm:w-[320px] select-none"
			style={{
				zIndex: 9999,
				...containerStyle,
			}}
		>
			<div ref={scrollContainerRef} className="max-h-[180px] sm:max-h-[280px] overflow-y-auto">
				{isLoading ? (
					<div className="py-1 px-2">
						<div className="px-3 py-2">
							<Skeleton className="h-[16px] w-24" />
						</div>
						{["a", "b", "c", "d", "e"].map((id, i) => (
							<div
								key={id}
								className={cn(
									"w-full flex items-center gap-2 px-3 py-2 text-left rounded-md",
									i >= 3 && "hidden sm:flex"
								)}
							>
								<span className="shrink-0">
									<Skeleton className="h-4 w-4" />
								</span>
								<span className="flex-1 text-sm">
									<Skeleton className="h-[20px]" style={{ width: `${60 + ((i * 7) % 30)}%` }} />
								</span>
							</div>
						))}
					</div>
				) : isError ? (
					<div className="py-1 px-2">
						<p className="px-3 py-2 text-xs text-destructive">Failed to load prompts</p>
					</div>
				) : filtered.length === 0 ? (
					<div className="py-1 px-2">
						<p className="px-3 py-2 text-xs text-muted-foreground">No matching prompts</p>
					</div>
				) : (
					<div className="py-1 px-2">
						<div className="px-3 py-2 text-xs font-bold text-muted-foreground/55">
							Saved Prompts
						</div>
						{filtered.map((action, index) => (
							<button
								key={action.id}
								ref={(el) => {
									if (el) itemRefs.current.set(index, el);
									else itemRefs.current.delete(index);
								}}
								type="button"
								onClick={() => handleSelect(index)}
								onMouseEnter={() => setHighlightedIndex(index)}
								className={cn(
									"w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors rounded-md cursor-pointer",
									index === highlightedIndex && "bg-accent"
								)}
							>
								<span className="shrink-0 text-muted-foreground">
									<Zap className="size-4" />
								</span>
								<span className="flex-1 text-sm truncate">{action.name}</span>
							</button>
						))}

						<div className="mx-2 my-1 border-t border-border dark:border-white/5" />
						<button
							ref={(el) => {
								if (el) itemRefs.current.set(createPromptIndex, el);
								else itemRefs.current.delete(createPromptIndex);
							}}
							type="button"
							onClick={() => handleSelect(createPromptIndex)}
							onMouseEnter={() => setHighlightedIndex(createPromptIndex)}
							className={cn(
								"w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors rounded-md cursor-pointer text-muted-foreground",
								highlightedIndex === createPromptIndex ? "bg-accent text-foreground" : "hover:text-foreground hover:bg-accent/50"
							)}
						>
							<span className="shrink-0">
								<Plus className="size-4" />
							</span>
							<span>Create prompt</span>
						</button>
					</div>
				)}
			</div>
		</div>
	);
});
