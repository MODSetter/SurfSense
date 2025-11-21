"use client";

import { Loader2 } from "lucide-react";
import { AnnouncementBanner } from "@/components/announcement-banner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { baseApiService } from "@/lib/apis/base-api.service";
import { AUTH_TOKEN_KEY } from "@/lib/constants";
import { useAuth } from "@/hooks/use-auth";
import { useEffect } from "react";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	const { isLoading, isAuthenticated } = useAuth();

	// Sync token with baseApiService when authenticated
	useEffect(() => {
		if (isAuthenticated && typeof window !== "undefined") {
			const token = localStorage.getItem(AUTH_TOKEN_KEY);
			if (token) {
				baseApiService.setBearerToken(token);
			}
		}
	}, [isAuthenticated]);

	// Show loading screen while verifying authentication
	if (isLoading) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">Loading Dashboard</CardTitle>
						<CardDescription>Verifying authentication...</CardDescription>
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
