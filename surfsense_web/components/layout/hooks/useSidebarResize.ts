"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const SIDEBAR_WIDTH_COOKIE_NAME = "sidebar_width";
const SIDEBAR_WIDTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

export const SIDEBAR_MIN_WIDTH = 240;
export const SIDEBAR_MAX_WIDTH = 480;

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

export function useSidebarResize(defaultWidth = SIDEBAR_MIN_WIDTH): UseSidebarResizeReturn {
	const [sidebarWidth, setSidebarWidth] = useState(defaultWidth);
	const [isDragging, setIsDragging] = useState(false);

	const startXRef = useRef(0);
	const startWidthRef = useRef(defaultWidth);
	const widthRef = useRef(defaultWidth);
	const pointerIdRef = useRef<number | null>(null);
	const captureTargetRef = useRef<HTMLElement | null>(null);

	useEffect(() => {
		try {
			const match = document.cookie.match(/(?:^|; )sidebar_width=([^;]+)/);
			if (match) {
				const parsed = Number(match[1]);
				if (!Number.isNaN(parsed) && parsed >= SIDEBAR_MIN_WIDTH && parsed <= SIDEBAR_MAX_WIDTH) {
					setSidebarWidth(parsed);
					widthRef.current = parsed;
				}
			}
		} catch {
		}
	}, []);

	const persistWidth = useCallback((width: number) => {
		try {
			// biome-ignore lint/suspicious/noDocumentCookie: SSR-readable preference, not security-sensitive
			document.cookie = `${SIDEBAR_WIDTH_COOKIE_NAME}=${width}; path=/; max-age=${SIDEBAR_WIDTH_COOKIE_MAX_AGE}`;
		} catch {
			// Ignore cookie write errors
		}
	}, []);

	const releaseCapture = useCallback(() => {
		const target = captureTargetRef.current;
		const pointerId = pointerIdRef.current;
		if (target && pointerId !== null) {
			try {
				if (target.hasPointerCapture(pointerId)) {
					target.releasePointerCapture(pointerId);
				}
			} catch {
			}
		}
		captureTargetRef.current = null;
		pointerIdRef.current = null;
	}, []);

	const handlePointerDown = useCallback(
		(e: React.PointerEvent<HTMLElement>) => {
			if (e.pointerType === "mouse" && e.button !== 0) return;

			e.preventDefault();
			const target = e.currentTarget;
			try {
				target.setPointerCapture(e.pointerId);
			} catch {
			}
			captureTargetRef.current = target;
			pointerIdRef.current = e.pointerId;
			startXRef.current = e.clientX;
			startWidthRef.current = widthRef.current;
			setIsDragging(true);
			setGlobalDragCursor(true);
		},
		[]
	);

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
