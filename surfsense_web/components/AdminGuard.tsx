"use client";

import { Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";

interface AdminGuardProps {
	children: React.ReactNode;
}

/**
 * AdminGuard component that ensures only superuser admins can access wrapped content
 * Automatically verifies authentication and superuser status
 * Redirects non-admins to dashboard and unauthorized users to login
 */
export function AdminGuard({ children }: AdminGuardProps) {
	const { isLoading } = useAuth(true); // requireSuperuser = true

	// Show loading state while verifying admin status
	if (isLoading) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">Verifying Access</CardTitle>
						<CardDescription>Checking administrator permissions...</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center py-6">
						<Loader2 className="h-12 w-12 text-primary animate-spin" />
					</CardContent>
				</Card>
			</div>
		);
	}

	// If we reach here, user is authenticated and is a superuser
	return <>{children}</>;
}
