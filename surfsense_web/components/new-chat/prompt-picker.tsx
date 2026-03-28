"use client";

import {
	BookOpen,
	Check,
	Globe,
	Languages,
	List,
	Minimize2,
	PenLine,
	Search,
	Zap,
} from "lucide-react";
import {
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useMemo,
	useRef,
	useState,
} from "react";

import type { PromptRead } from "@/contracts/types/prompts.types";
import { promptsApiService } from "@/lib/apis/prompts-api.service";
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

const ICONS: Record<string, React.ReactNode> = {
	check: <Check className="size-3.5" />,
	minimize: <Minimize2 className="size-3.5" />,
	languages: <Languages className="size-3.5" />,
	"pen-line": <PenLine className="size-3.5" />,
	"book-open": <BookOpen className="size-3.5" />,
	list: <List className="size-3.5" />,
	search: <Search className="size-3.5" />,
	globe: <Globe className="size-3.5" />,
	zap: <Zap className="size-3.5" />,
};

const DEFAULT_ACTIONS: { name: string; prompt: string; mode: "transform" | "explore"; icon: string }[] = [
	{ name: "Fix grammar", prompt: "Fix the grammar and spelling in the following text. Return only the corrected text, nothing else.\n\n{selection}", mode: "transform", icon: "check" },
	{ name: "Make shorter", prompt: "Make the following text more concise while preserving its meaning. Return only the shortened text, nothing else.\n\n{selection}", mode: "transform", icon: "minimize" },
	{ name: "Translate", prompt: "Translate the following text to English. If it is already in English, translate it to French. Return only the translation, nothing else.\n\n{selection}", mode: "transform", icon: "languages" },
	{ name: "Rewrite", prompt: "Rewrite the following text to improve clarity and readability. Return only the rewritten text, nothing else.\n\n{selection}", mode: "transform", icon: "pen-line" },
	{ name: "Summarize", prompt: "Summarize the following text concisely. Return only the summary, nothing else.\n\n{selection}", mode: "transform", icon: "list" },
	{ name: "Explain", prompt: "Explain the following text in simple terms:\n\n{selection}", mode: "explore", icon: "book-open" },
	{ name: "Ask my knowledge base", prompt: "Search my knowledge base for information related to:\n\n{selection}", mode: "explore", icon: "search" },
	{ name: "Look up on the web", prompt: "Search the web for information about:\n\n{selection}", mode: "explore", icon: "globe" },
];

export const PromptPicker = forwardRef<PromptPickerRef, PromptPickerProps>(
	function PromptPicker({ onSelect, onDone, externalSearch = "", containerStyle }, ref) {
		const [highlightedIndex, setHighlightedIndex] = useState(0);
		const [customPrompts, setCustomPrompts] = useState<PromptRead[]>([]);
		const scrollContainerRef = useRef<HTMLDivElement>(null);
		const shouldScrollRef = useRef(false);
		const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

		useEffect(() => {
			promptsApiService.list().then(setCustomPrompts).catch(() => {});
		}, []);

		const allActions = useMemo(() => {
			const customs = customPrompts.map((a) => ({
				name: a.name,
				prompt: a.prompt,
				mode: a.mode as "transform" | "explore",
				icon: a.icon || "zap",
			}));
			return [...DEFAULT_ACTIONS, ...customs];
		}, [customPrompts]);

		const filtered = useMemo(() => {
			if (!externalSearch) return allActions;
			return allActions.filter((a) =>
				a.name.toLowerCase().includes(externalSearch.toLowerCase())
			);
		}, [allActions, externalSearch]);

		// Reset highlight when results change
		const prevSearchRef = useRef(externalSearch);
		if (prevSearchRef.current !== externalSearch) {
			prevSearchRef.current = externalSearch;
			if (highlightedIndex !== 0) {
				setHighlightedIndex(0);
			}
		}

		const handleSelect = useCallback(
			(index: number) => {
				const action = filtered[index];
				if (!action) return;
				onSelect({ name: action.name, prompt: action.prompt, mode: action.mode });
				onDone();
			},
			[filtered, onSelect, onDone]
		);

		// Auto-scroll highlighted item into view
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
					setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : filtered.length - 1));
				},
				moveDown: () => {
					shouldScrollRef.current = true;
					setHighlightedIndex((prev) => (prev < filtered.length - 1 ? prev + 1 : 0));
				},
			}),
			[filtered.length, highlightedIndex, handleSelect]
		);

		if (filtered.length === 0) return null;

		return (
			<div
				className="w-64 rounded-lg border bg-popover shadow-lg overflow-hidden"
				style={containerStyle}
			>
				<div ref={scrollContainerRef} className="max-h-48 overflow-y-auto py-1">
					{filtered.map((action, index) => (
						<button
							key={action.name}
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
							<span className="text-muted-foreground">{ICONS[action.icon] ?? <Zap className="size-3.5" />}</span>
							<span className="truncate">{action.name}</span>
						</button>
					))}
				</div>
			</div>
		);
	}
);
