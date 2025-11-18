"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnnouncementBanner } from "@/components/announcement-banner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { baseApiService } from "@/lib/apis/base-api.service";
import { AUTH_TOKEN_KEY } from "@/lib/constants";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	const router = useRouter();
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);

	useEffect(() => {
		// Check if user is authenticated
		const token = localStorage.getItem(AUTH_TOKEN_KEY);
		if (!token) {
			router.push("/login");
			return;
		}
		// Ensure the baseApiService has the correct token
		// This handles cases where the page is refreshed or navigated to directly
		baseApiService.setBearerToken(token);
		setIsCheckingAuth(false);
	}, [router]);

	// Show loading screen while checking authentication
	if (isCheckingAuth) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">Loading Dashboard</CardTitle>
						<CardDescription>Checking authentication...</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center py-6">
						<Loader2 className="h-12 w-12 text-primary animate-spin" />
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="h-full flex flex-col ">
			<AnnouncementBanner />
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
