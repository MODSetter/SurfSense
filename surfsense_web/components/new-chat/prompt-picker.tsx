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
import { Spinner } from "@/components/ui/spinner";
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

	const handleSelect = useCallback(
		(index: number) => {
			const action = filtered[index];
			if (!action) return;
			onSelect({ name: action.name, prompt: action.prompt, mode: action.mode });
		},
		[filtered, onSelect]
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
				if (filtered.length === 0) return;
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : filtered.length - 1));
			},
			moveDown: () => {
				if (filtered.length === 0) return;
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev < filtered.length - 1 ? prev + 1 : 0));
			},
		}),
		[filtered.length, highlightedIndex, handleSelect]
	);

	return (
		<div
			className="w-64 rounded-lg border bg-popover shadow-lg overflow-hidden"
			style={containerStyle}
		>
			<div ref={scrollContainerRef} className="max-h-48 overflow-y-auto py-1">
				{isLoading ? (
					<div className="flex items-center justify-center py-3">
						<Spinner className="size-4" />
					</div>
				) : isError ? (
					<p className="px-3 py-2 text-xs text-destructive">Failed to load prompts</p>
				) : filtered.length === 0 ? (
					<p className="px-3 py-2 text-xs text-muted-foreground">No matching prompts</p>
				) : (
					filtered.map((action, index) => (
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
								"flex w-full items-center gap-2 px-3 py-1.5 text-sm cursor-pointer",
								index === highlightedIndex ? "bg-accent" : "hover:bg-accent/50"
							)}
						>
							<span className="text-muted-foreground">
								<Zap className="size-3.5" />
							</span>
							<span className="truncate">{action.name}</span>
						</button>
					))
				)}

				<div className="my-1 h-px bg-border mx-2" />
				<button
					type="button"
					onClick={() => {
						onDone();
						setUserSettingsDialog({ open: true, initialTab: "prompts" });
					}}
					className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/50 cursor-pointer"
				>
					<Plus className="size-3.5" />
					<span>Create prompt</span>
				</button>
			</div>
		</div>
	);
});
