"use client";

import { useEffect, useState } from "react";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);

	// Use the global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(isCheckingAuth);

	useEffect(() => {
		// Check if user is authenticated
		const token = getBearerToken();
		if (!token) {
			// Save current path and redirect to login
			redirectToLogin();
			return;
		}
		setIsCheckingAuth(false);
	}, []);

	// Return null while loading - the global provider handles the loading UI
	if (isCheckingAuth) {
		return null;
	}

	return (
		<div className="h-full flex flex-col ">
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
