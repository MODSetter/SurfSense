"use client";

import { useEffect, useState } from "react";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { ensureTokensFromElectron, getBearerToken, redirectToLogin } from "@/lib/auth-utils";
import { queryClient } from "@/lib/query-client/client";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);

	// Use the global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(isCheckingAuth);

	useEffect(() => {
		async function checkAuth() {
			let token = getBearerToken();
			if (!token) {
				const synced = await ensureTokensFromElectron();
				if (synced) token = getBearerToken();
			}
			if (!token) {
				redirectToLogin();
				return;
			}
			queryClient.invalidateQueries({ queryKey: [...USER_QUERY_KEY] });
			setIsCheckingAuth(false);
		}
		checkAuth();
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
