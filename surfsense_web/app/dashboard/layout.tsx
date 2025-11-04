"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnnouncementBanner } from "@/components/announcement-banner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	const router = useRouter();
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);

	useEffect(() => {
		// Check if user is authenticated
		const token = localStorage.getItem("surfsense_bearer_token");
		if (!token) {
			router.push("/login");
			return;
		}
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
		<>
			<AnnouncementBanner />
			{children}
		</>
	);
}
