"use client";

import { useReducedMotion } from "motion/react";
import {
	type KeyboardEventHandler,
	type PointerEventHandler,
	type UIEventHandler,
	useCallback,
	useEffect,
	useRef,
	useState,
	type WheelEventHandler,
} from "react";

type ScrollMetrics = Pick<HTMLElement, "clientHeight" | "scrollHeight" | "scrollTop">;
export type ReasoningScrollMode = "following" | "manual";

export function isReasoningAtBottom(element: ScrollMetrics, threshold = 8): boolean {
	return element.scrollHeight - element.clientHeight - element.scrollTop <= threshold;
}

export function resolveReasoningScrollMode(
	currentMode: ReasoningScrollMode,
	element: ScrollMetrics,
	programmatic: boolean
): ReasoningScrollMode {
	if (programmatic) return currentMode;
	return isReasoningAtBottom(element) ? "following" : "manual";
}

export function useReasoningAutoScroll(text: string, running: boolean) {
	const scrollRef = useRef<HTMLDivElement>(null);
	const followsBottomRef = useRef(true);
	const wasRunningRef = useRef(running);
	const programmaticScrollRef = useRef(false);
	const hasContentAboveRef = useRef(false);
	const hasContentBelowRef = useRef(false);
	const [scrollMode, setScrollMode] = useState<ReasoningScrollMode>("following");
	const [hasContentAbove, setHasContentAbove] = useState(false);
	const [hasContentBelow, setHasContentBelow] = useState(false);
	const reducedMotion = useReducedMotion();

	const updateScrollMode = useCallback((mode: ReasoningScrollMode) => {
		if (followsBottomRef.current === (mode === "following")) return;
		followsBottomRef.current = mode === "following";
		setScrollMode(mode);
	}, []);

	const updateScrollEdges = useCallback((element: HTMLDivElement) => {
		const nextHasContentAbove = element.scrollTop > 0;
		if (hasContentAboveRef.current !== nextHasContentAbove) {
			hasContentAboveRef.current = nextHasContentAbove;
			setHasContentAbove(nextHasContentAbove);
		}

		const nextHasContentBelow = !isReasoningAtBottom(element);
		if (hasContentBelowRef.current !== nextHasContentBelow) {
			hasContentBelowRef.current = nextHasContentBelow;
			setHasContentBelow(nextHasContentBelow);
		}
	}, []);

	const handleScroll = useCallback<UIEventHandler<HTMLDivElement>>(
		(event) => {
			updateScrollEdges(event.currentTarget);
			updateScrollMode(
				resolveReasoningScrollMode(
					followsBottomRef.current ? "following" : "manual",
					event.currentTarget,
					programmaticScrollRef.current
				)
			);
		},
		[updateScrollEdges, updateScrollMode]
	);

	const handleWheel = useCallback<WheelEventHandler<HTMLDivElement>>(
		(event) => {
			programmaticScrollRef.current = false;
			if (event.deltaY < 0 && event.currentTarget.scrollTop > 0) {
				updateScrollMode("manual");
			}
		},
		[updateScrollMode]
	);

	const handlePointerDown = useCallback<PointerEventHandler<HTMLDivElement>>(() => {
		programmaticScrollRef.current = false;
	}, []);

	const handleKeyDown = useCallback<KeyboardEventHandler<HTMLDivElement>>(
		(event) => {
			switch (event.key) {
				case "ArrowUp":
				case "Home":
				case "PageUp":
					programmaticScrollRef.current = false;
					if (event.currentTarget.scrollTop > 0) updateScrollMode("manual");
					return;
				case " ":
					programmaticScrollRef.current = false;
					if (event.shiftKey && event.currentTarget.scrollTop > 0) {
						updateScrollMode("manual");
					}
					return;
				case "ArrowDown":
				case "End":
				case "PageDown":
					programmaticScrollRef.current = false;
					return;
				default:
					return;
			}
		},
		[updateScrollMode]
	);

	useEffect(() => {
		const shouldFollow = running || wasRunningRef.current;
		wasRunningRef.current = running;
		const element = scrollRef.current;
		if (element) updateScrollEdges(element);
		if (text.length === 0 || !shouldFollow || !followsBottomRef.current) return;

		const frame = requestAnimationFrame(() => {
			const element = scrollRef.current;
			if (!element || !followsBottomRef.current) return;
			programmaticScrollRef.current = true;
			element.scrollTo({
				top: element.scrollHeight,
				behavior: reducedMotion ? "auto" : "smooth",
			});
		});

		return () => cancelAnimationFrame(frame);
	}, [reducedMotion, running, text, updateScrollEdges]);

	return {
		scrollRef,
		hasContentAbove,
		hasContentBelow,
		scrollMode,
		handleKeyDown,
		handlePointerDown,
		handleScroll,
		handleWheel,
	};
}
