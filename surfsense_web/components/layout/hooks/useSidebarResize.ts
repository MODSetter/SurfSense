"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const SIDEBAR_WIDTH_COOKIE_NAME = "sidebar_width";
const SIDEBAR_WIDTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

export const SIDEBAR_MIN_WIDTH = 240;
export const SIDEBAR_MAX_WIDTH = 480;

interface UseSidebarResizeReturn {
	sidebarWidth: number;
	handleMouseDown: (e: React.MouseEvent) => void;
	isDragging: boolean;
}

export function useSidebarResize(defaultWidth = SIDEBAR_MIN_WIDTH): UseSidebarResizeReturn {
	const [sidebarWidth, setSidebarWidth] = useState(defaultWidth);
	const [isDragging, setIsDragging] = useState(false);

	const startXRef = useRef(0);
	const startWidthRef = useRef(defaultWidth);

	// Initialize from cookie on mount
	useEffect(() => {
		try {
			const match = document.cookie.match(/(?:^|; )sidebar_width=([^;]+)/);
			if (match) {
				const parsed = Number(match[1]);
				if (!Number.isNaN(parsed) && parsed >= SIDEBAR_MIN_WIDTH && parsed <= SIDEBAR_MAX_WIDTH) {
					setSidebarWidth(parsed);
				}
			}
		} catch {
			// Ignore cookie read errors
		}
	}, []);

	// Persist width to cookie
	const persistWidth = useCallback((width: number) => {
		try {
			document.cookie = `${SIDEBAR_WIDTH_COOKIE_NAME}=${width}; path=/; max-age=${SIDEBAR_WIDTH_COOKIE_MAX_AGE}`;
		} catch {
			// Ignore cookie write errors
		}
	}, []);

	const handleMouseDown = useCallback(
		(e: React.MouseEvent) => {
			e.preventDefault();
			startXRef.current = e.clientX;
			startWidthRef.current = sidebarWidth;
			setIsDragging(true);

			document.body.style.cursor = "col-resize";
			document.body.style.userSelect = "none";
		},
		[sidebarWidth]
	);

	useEffect(() => {
		if (!isDragging) return;

		const handleMouseMove = (e: MouseEvent) => {
			const delta = e.clientX - startXRef.current;
			const newWidth = Math.min(
				SIDEBAR_MAX_WIDTH,
				Math.max(SIDEBAR_MIN_WIDTH, startWidthRef.current + delta)
			);
			setSidebarWidth(newWidth);
		};

		const handleMouseUp = () => {
			setIsDragging(false);
			document.body.style.cursor = "";
			document.body.style.userSelect = "";

			// Persist the final width
			setSidebarWidth((currentWidth) => {
				persistWidth(currentWidth);
				return currentWidth;
			});
		};

		document.addEventListener("mousemove", handleMouseMove);
		document.addEventListener("mouseup", handleMouseUp);

		return () => {
			document.removeEventListener("mousemove", handleMouseMove);
			document.removeEventListener("mouseup", handleMouseUp);
			document.body.style.cursor = "";
			document.body.style.userSelect = "";
		};
	}, [isDragging, persistWidth]);

	return {
		sidebarWidth,
		handleMouseDown,
		isDragging,
	};
}
