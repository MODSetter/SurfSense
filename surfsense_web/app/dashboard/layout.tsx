"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { UnifiedLoadingScreen } from "@/components/ui/unified-loading-screen";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	const t = useTranslations("dashboard");
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);

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

	// Show loading screen while checking authentication
	if (isCheckingAuth) {
		return <UnifiedLoadingScreen variant="default" message={t("checking_auth")} />;
	}

	return (
		<div className="h-full flex flex-col ">
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
