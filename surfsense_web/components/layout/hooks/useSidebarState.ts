"use client";

import { useCallback, useEffect, useState } from "react";
import { persistSidebarPreference, SIDEBAR_COLLAPSED_COOKIE } from "../sidebar-preferences";

interface UseSidebarStateReturn {
	isCollapsed: boolean;
	setIsCollapsed: (collapsed: boolean) => void;
	toggleCollapsed: () => void;
}

export function useSidebarState(initialCollapsed: boolean): UseSidebarStateReturn {
	const [isCollapsed, setIsCollapsedState] = useState(initialCollapsed);

	// Persist to cookie when state changes
	const setIsCollapsed = useCallback((collapsed: boolean) => {
		setIsCollapsedState(collapsed);
		persistSidebarPreference(SIDEBAR_COLLAPSED_COOKIE, collapsed);
	}, []);

	const toggleCollapsed = useCallback(() => {
		setIsCollapsedState((prev: boolean) => {
			const next = !prev;
			persistSidebarPreference(SIDEBAR_COLLAPSED_COOKIE, next);
			return next;
		});
	}, []);

	// Keyboard shortcut: Cmd/Ctrl + \
	useEffect(() => {
		const handleKeyDown = (event: KeyboardEvent) => {
			if (event.key === "\\" && (event.metaKey || event.ctrlKey)) {
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
