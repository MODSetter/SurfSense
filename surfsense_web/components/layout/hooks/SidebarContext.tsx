"use client";

import { createContext, type ReactNode, useContext } from "react";

interface SidebarContextValue {
	isCollapsed: boolean;
	setIsCollapsed: (collapsed: boolean) => void;
	toggleCollapsed: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

interface SidebarProviderProps {
	children: ReactNode;
	value: SidebarContextValue;
}

export function SidebarProvider({ children, value }: SidebarProviderProps) {
	return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
}

export function useSidebarContext(): SidebarContextValue {
	const context = useContext(SidebarContext);
	if (!context) {
		throw new Error("useSidebarContext must be used within a SidebarProvider");
	}
	return context;
}

/**
 * Safe version that returns null if not within provider
 * Useful for components that may be rendered outside the sidebar context
 */
export function useSidebarContextSafe(): SidebarContextValue | null {
	return useContext(SidebarContext);
}
