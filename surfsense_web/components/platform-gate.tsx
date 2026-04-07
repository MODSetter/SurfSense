"use client";

import type { ReactNode } from "react";
import { usePlatform } from "@/hooks/use-platform";

export function DesktopOnly({ children }: { children: ReactNode }) {
	const { isDesktop } = usePlatform();
	if (!isDesktop) return null;
	return <>{children}</>;
}

export function WebOnly({ children }: { children: ReactNode }) {
	const { isWeb } = usePlatform();
	if (!isWeb) return null;
	return <>{children}</>;
}
