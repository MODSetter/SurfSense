"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
	persistSidebarPreference,
	SIDEBAR_MAX_WIDTH,
	SIDEBAR_MIN_WIDTH,
	SIDEBAR_WIDTH_COOKIE,
} from "../sidebar-preferences";

interface UseSidebarResizeReturn {
	sidebarWidth: number;
	handlePointerDown: (e: React.PointerEvent<HTMLElement>) => void;
	isDragging: boolean;
}

function setGlobalDragCursor(active: boolean) {
	const html = document.documentElement;
	const body = document.body;
	if (active) {
		html.style.cursor = "col-resize";
		body.style.cursor = "col-resize";
		html.style.userSelect = "none";
		body.style.userSelect = "none";
	} else {
		html.style.cursor = "";
		body.style.cursor = "";
		html.style.userSelect = "";
		body.style.userSelect = "";
	}
}

export function useSidebarResize(initialWidth: number): UseSidebarResizeReturn {
	const [sidebarWidth, setSidebarWidth] = useState(initialWidth);
	const [isDragging, setIsDragging] = useState(false);

	const startXRef = useRef(0);
	const startWidthRef = useRef(initialWidth);
	const widthRef = useRef(initialWidth);
	const pointerIdRef = useRef<number | null>(null);
	const captureTargetRef = useRef<HTMLElement | null>(null);

	const persistWidth = useCallback((width: number) => {
		persistSidebarPreference(SIDEBAR_WIDTH_COOKIE, width);
	}, []);

	const releaseCapture = useCallback(() => {
		const target = captureTargetRef.current;
		const pointerId = pointerIdRef.current;
		if (target && pointerId !== null) {
			try {
				if (target.hasPointerCapture(pointerId)) {
					target.releasePointerCapture(pointerId);
				}
			} catch {}
		}
		captureTargetRef.current = null;
		pointerIdRef.current = null;
	}, []);

	const handlePointerDown = useCallback((e: React.PointerEvent<HTMLElement>) => {
		if (e.pointerType === "mouse" && e.button !== 0) return;

		e.preventDefault();
		const target = e.currentTarget;
		try {
			target.setPointerCapture(e.pointerId);
		} catch {}
		captureTargetRef.current = target;
		pointerIdRef.current = e.pointerId;
		startXRef.current = e.clientX;
		startWidthRef.current = widthRef.current;
		setIsDragging(true);
		setGlobalDragCursor(true);
	}, []);

	useEffect(() => {
		if (!isDragging) return;

		const handlePointerMove = (e: PointerEvent) => {
			if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) return;
			const delta = e.clientX - startXRef.current;
			const newWidth = Math.min(
				SIDEBAR_MAX_WIDTH,
				Math.max(SIDEBAR_MIN_WIDTH, startWidthRef.current + delta)
			);
			if (newWidth !== widthRef.current) {
				widthRef.current = newWidth;
				setSidebarWidth(newWidth);
			}
		};

		const stop = (e: PointerEvent) => {
			if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) return;
			releaseCapture();
			setIsDragging(false);
			setGlobalDragCursor(false);
			persistWidth(widthRef.current);
		};

		window.addEventListener("pointermove", handlePointerMove);
		window.addEventListener("pointerup", stop);
		window.addEventListener("pointercancel", stop);

		return () => {
			window.removeEventListener("pointermove", handlePointerMove);
			window.removeEventListener("pointerup", stop);
			window.removeEventListener("pointercancel", stop);
			setGlobalDragCursor(false);
			releaseCapture();
		};
	}, [isDragging, persistWidth, releaseCapture]);

	return {
		sidebarWidth,
		handlePointerDown,
		isDragging,
	};
}
