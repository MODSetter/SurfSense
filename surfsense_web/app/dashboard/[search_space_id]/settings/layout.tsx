import type React from "react";

/**
 * Settings layout - renders children directly without the parent sidebar
 * This creates a full-screen settings experience
 */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
	return <div className="fixed inset-0 z-50 bg-background">{children}</div>;
}
