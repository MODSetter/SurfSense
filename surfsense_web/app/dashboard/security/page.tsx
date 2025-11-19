"use client";

import { ArrowLeft, Shield, ShieldCheck, ShieldOff } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/DashboardHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { useUser } from "@/hooks";

export default function SecurityPage() {
	const { user, loading, error } = useUser();

	const customUser = {
		name: user?.email ? user.email.split("@")[0] : "User",
		email: user?.email || (error ? "Error loading user" : "Unknown User"),
		avatar: "/icon-128.png",
	};

	if (loading) {
		return (
			<div className="flex flex-col justify-center items-center min-h-screen">
				<div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
				<p className="text-muted-foreground">Loading Security Settings...</p>
			</div>
		);
	}

	if (error) {
		return (
			<div className="container mx-auto py-10">
				<Alert variant="destructive">
					<AlertTitle>Error</AlertTitle>
					<AlertDescription>{error}</AlertDescription>
				</Alert>
			</div>
		);
	}

	return (
		<div className="container mx-auto py-10">
			<div className="flex flex-col space-y-6">
				<DashboardHeader
					title="Security Settings"
					description="Manage your account security and two-factor authentication"
					user={customUser}
					isAdmin={user?.is_superuser ?? false}
				/>

				<div className="mb-4">
					<Link href="/dashboard">
						<Button variant="ghost" size="sm">
							<ArrowLeft className="mr-2 h-4 w-4" />
							Back to Dashboard
						</Button>
					</Link>
				</div>

				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Shield className="h-5 w-5" />
							Two-Factor Authentication (2FA)
						</CardTitle>
						<CardDescription>
							Add an extra layer of security to your account by enabling two-factor authentication
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex items-center justify-between p-4 border rounded-lg">
							<div className="flex items-center gap-3">
								<ShieldOff className="h-8 w-8 text-muted-foreground" />
								<div>
									<p className="font-medium">2FA Status</p>
									<p className="text-sm text-muted-foreground">
										Two-factor authentication is not enabled
									</p>
								</div>
							</div>
							<Button disabled>
								Enable 2FA
							</Button>
						</div>
						<Alert>
							<ShieldCheck className="h-4 w-4" />
							<AlertTitle>Coming Soon</AlertTitle>
							<AlertDescription>
								Two-factor authentication setup will be available in a future update.
								This will allow you to use an authenticator app (like Google Authenticator or Authy)
								to generate time-based codes for additional security.
							</AlertDescription>
						</Alert>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
