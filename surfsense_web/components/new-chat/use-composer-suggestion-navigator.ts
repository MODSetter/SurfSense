"use client";

import type * as React from "react";
import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";

export type ComposerSuggestionNode<TValue> = {
	id: string;
	label: string;
	subtitle?: string;
	icon?: React.ReactNode;
	keywords?: string[];
	type: "branch" | "item" | "action";
	value?: TValue;
	disabled?: boolean;
};

export type ComposerSuggestionNavigatorRef = {
	selectHighlighted: () => void;
	moveUp: () => void;
	moveDown: () => void;
	goBack: () => boolean;
};

export type ComposerSuggestionNavigatorOptions<TValue> = {
	nodes: ComposerSuggestionNode<TValue>[];
	onSelect: (node: ComposerSuggestionNode<TValue>) => void;
	onBack?: () => boolean;
	ref?: React.Ref<ComposerSuggestionNavigatorRef>;
};

export function useComposerSuggestionNavigator<TValue>({
	nodes,
	onSelect,
	onBack,
	ref,
}: ComposerSuggestionNavigatorOptions<TValue>) {
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const shouldScrollRef = useRef(false);
	const nodesKey = useMemo(() => nodes.map((node) => node.id).join("\u0000"), [nodes]);
	const previousNodesKeyRef = useRef<string | null>(null);

	// Reset keyboard focus when the caller swaps the visible node set.
	useEffect(() => {
		if (previousNodesKeyRef.current === nodesKey) return;
		previousNodesKeyRef.current = nodesKey;
		setHighlightedIndex(0);
		itemRefs.current.clear();
	}, [nodesKey]);

	useEffect(() => {
		if (!shouldScrollRef.current) return;
		shouldScrollRef.current = false;

		const rafId = requestAnimationFrame(() => {
			const item = itemRefs.current.get(highlightedIndex);
			const container = scrollContainerRef.current;
			if (!item || !container) return;

			const itemRect = item.getBoundingClientRect();
			const containerRect = container.getBoundingClientRect();
			if (itemRect.top < containerRect.top || itemRect.bottom > containerRect.bottom) {
				item.scrollIntoView({ block: "nearest" });
			}
		});

		return () => cancelAnimationFrame(rafId);
	}, [highlightedIndex]);

	const moveUp = useCallback(() => {
		if (nodes.length === 0) return;
		shouldScrollRef.current = true;
		setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : nodes.length - 1));
	}, [nodes.length]);

	const moveDown = useCallback(() => {
		if (nodes.length === 0) return;
		shouldScrollRef.current = true;
		setHighlightedIndex((prev) => (prev < nodes.length - 1 ? prev + 1 : 0));
	}, [nodes.length]);

	const selectHighlighted = useCallback(() => {
		const node = nodes[highlightedIndex];
		if (!node || node.disabled) return;
		onSelect(node);
	}, [highlightedIndex, nodes, onSelect]);

	const goBack = useCallback(() => onBack?.() ?? false, [onBack]);

	useImperativeHandle(
		ref,
		() => ({
			selectHighlighted,
			moveUp,
			moveDown,
			goBack,
		}),
		[goBack, moveDown, moveUp, selectHighlighted]
	);

	const getItemRef = useCallback(
		(index: number) => (el: HTMLButtonElement | null) => {
			if (el) itemRefs.current.set(index, el);
			else itemRefs.current.delete(index);
		},
		[]
	);

	return {
		highlightedIndex,
		setHighlightedIndex,
		scrollContainerRef,
		getItemRef,
		moveUp,
		moveDown,
		selectHighlighted,
		goBack,
	};
}
