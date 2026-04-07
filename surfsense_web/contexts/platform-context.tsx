"use client";

import { createContext, type ReactNode, useEffect, useState } from "react";

export interface PlatformContextValue {
	isDesktop: boolean;
	isWeb: boolean;
	electronAPI: ElectronAPI | null;
}

const SSR_VALUE: PlatformContextValue = {
	isDesktop: false,
	isWeb: false,
	electronAPI: null,
};

export const PlatformContext = createContext<PlatformContextValue>(SSR_VALUE);

export function PlatformProvider({ children }: { children: ReactNode }) {
	const [value, setValue] = useState<PlatformContextValue>(SSR_VALUE);

	useEffect(() => {
		const api = window.electronAPI ?? null;
		const isDesktop = !!api;
		setValue({ isDesktop, isWeb: !isDesktop, electronAPI: api });
	}, []);

	return <PlatformContext.Provider value={value}>{children}</PlatformContext.Provider>;
}
