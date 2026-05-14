"use client";

import type { ComponentProps, HTMLAttributes, ReactElement, ReactNode } from "react";
import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import { useMediaQuery } from "@/hooks/use-media-query";
import { Popover, PopoverContent, PopoverTrigger } from "./_adapter";

type PopoverContentProps = ComponentProps<typeof PopoverContent>;

export type CitationHoverTriggerProps = Pick<
	HTMLAttributes<HTMLElement>,
	"onBlur" | "onFocus" | "onPointerEnter" | "onPointerLeave"
>;

interface CitationHoverPopoverProps {
	id: string;
	trigger: (props: CitationHoverTriggerProps) => ReactElement;
	children: ReactNode;
	contentClassName?: string;
	side?: PopoverContentProps["side"];
	align?: PopoverContentProps["align"];
	sideOffset?: PopoverContentProps["sideOffset"];
	onContentClick?: PopoverContentProps["onClick"];
}

const OPEN_DELAY_MS = 80;
const CLOSE_DELAY_MS = 120;

let activeCitationId: string | null = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

function getSnapshot() {
	return activeCitationId;
}

function setActiveCitationId(id: string | null) {
	if (activeCitationId === id) return;
	activeCitationId = id;
	for (const listener of listeners) {
		listener();
	}
}

function useCitationHoverState(id: string) {
	const activeId = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
	const openTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const clearTimers = useCallback(() => {
		if (openTimerRef.current) {
			clearTimeout(openTimerRef.current);
			openTimerRef.current = null;
		}
		if (closeTimerRef.current) {
			clearTimeout(closeTimerRef.current);
			closeTimerRef.current = null;
		}
	}, []);

	const open = activeId === id;

	const scheduleOpen = useCallback(() => {
		clearTimers();
		openTimerRef.current = setTimeout(() => {
			setActiveCitationId(id);
			openTimerRef.current = null;
		}, OPEN_DELAY_MS);
	}, [clearTimers, id]);

	const scheduleClose = useCallback(() => {
		clearTimers();
		closeTimerRef.current = setTimeout(() => {
			if (activeCitationId === id) {
				setActiveCitationId(null);
			}
			closeTimerRef.current = null;
		}, CLOSE_DELAY_MS);
	}, [clearTimers, id]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			clearTimers();
			setActiveCitationId(nextOpen ? id : null);
		},
		[clearTimers, id]
	);

	useEffect(() => {
		return () => {
			clearTimers();
			if (activeCitationId === id) {
				setActiveCitationId(null);
			}
		};
	}, [clearTimers, id]);

	return { open, scheduleOpen, scheduleClose, handleOpenChange };
}

export function CitationHoverPopover({
	id,
	trigger,
	children,
	contentClassName,
	side = "top",
	align = "start",
	sideOffset = 6,
	onContentClick,
}: CitationHoverPopoverProps) {
	const isTouchLike = useMediaQuery("(hover: none), (pointer: coarse)");
	const { open, scheduleOpen, scheduleClose, handleOpenChange } = useCitationHoverState(id);
	const hoverProps = {
		onPointerEnter: scheduleOpen,
		onPointerLeave: scheduleClose,
		onFocus: scheduleOpen,
		onBlur: scheduleClose,
	} satisfies CitationHoverTriggerProps;

	if (isTouchLike) {
		return trigger({});
	}

	return (
		<Popover open={open} onOpenChange={handleOpenChange}>
			<PopoverTrigger asChild>{trigger(hoverProps)}</PopoverTrigger>
			<PopoverContent
				side={side}
				align={align}
				sideOffset={sideOffset}
				className={contentClassName}
				onPointerEnter={scheduleOpen}
				onPointerLeave={scheduleClose}
				onOpenAutoFocus={(event) => event.preventDefault()}
				onCloseAutoFocus={(event) => event.preventDefault()}
				onClick={onContentClick}
			>
				{children}
			</PopoverContent>
		</Popover>
	);
}
