"use client";

import { useCallback, useEffect, useState } from "react";

const SIDEBAR_COOKIE_NAME = "sidebar_collapsed";
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

interface UseSidebarStateReturn {
	isCollapsed: boolean;
	setIsCollapsed: (collapsed: boolean) => void;
	toggleCollapsed: () => void;
}

export function useSidebarState(defaultCollapsed = false): UseSidebarStateReturn {
	const [isCollapsed, setIsCollapsedState] = useState(defaultCollapsed);

	// Initialize from cookie on mount
	useEffect(() => {
		try {
			const match = document.cookie.match(/(?:^|; )sidebar_collapsed=([^;]+)/);
			if (match) {
				setIsCollapsedState(match[1] === "true");
			}
		} catch {
			// Ignore cookie read errors
		}
	}, []);

	// Persist to cookie when state changes
	const setIsCollapsed = useCallback((collapsed: boolean) => {
		setIsCollapsedState(collapsed);
		try {
			document.cookie = `${SIDEBAR_COOKIE_NAME}=${collapsed}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
		} catch {
			// Ignore cookie write errors
		}
	}, []);

	const toggleCollapsed = useCallback(() => {
		setIsCollapsed(!isCollapsed);
	}, [isCollapsed, setIsCollapsed]);

	// Keyboard shortcut: Cmd/Ctrl + B
	useEffect(() => {
		const handleKeyDown = (event: KeyboardEvent) => {
			if (event.key === "b" && (event.metaKey || event.ctrlKey)) {
				event.preventDefault();
				toggleCollapsed();
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [toggleCollapsed]);

	return {
		isCollapsed,
		setIsCollapsed,
		toggleCollapsed,
	};
}
