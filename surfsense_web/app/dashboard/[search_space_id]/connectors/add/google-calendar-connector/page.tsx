"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, ExternalLink, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	type SearchSourceConnector,
	useSearchSourceConnectors,
} from "@/hooks/use-search-source-connectors";

export default function GoogleCalendarConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isConnecting, setIsConnecting] = useState(false);
	const [doesConnectorExist, setDoesConnectorExist] = useState(false);

	const { fetchConnectors } = useSearchSourceConnectors(true, parseInt(searchSpaceId));

	useEffect(() => {
		fetchConnectors(parseInt(searchSpaceId)).then((data) => {
			const connector = data.find(
				(c: SearchSourceConnector) =>
					c.connector_type === EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR
			);
			if (connector) {
				setDoesConnectorExist(true);
			}
		});
	}, []);

	// Handle Google OAuth connection
	const handleConnectGoogle = async () => {
		try {
			setIsConnecting(true);
			// Call backend to initiate authorization flow
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/auth/google/calendar/connector/add/?space_id=${searchSpaceId}`,
				{
					method: "GET",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
				}
			);

			if (!response.ok) {
				throw new Error("Failed to initiate Google OAuth");
			}

			const data = await response.json();

			// Redirect to Google for authentication
			window.location.href = data.auth_url;
		} catch (error) {
			console.error("Error connecting to Google:", error);
			toast.error("Failed to connect to Google Calendar");
		} finally {
			setIsConnecting(false);
		}
	};

	return (
		<div className="container mx-auto py-8 max-w-2xl">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				{/* Header */}
				<div className="mb-8">
					<Link
						href={`/dashboard/${searchSpaceId}/connectors/add`}
						className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
					>
						<ArrowLeft className="mr-2 h-4 w-4" />
						Back to connectors
					</Link>
					<div className="flex items-center gap-4">
						<div className="flex h-12 w-12 items-center justify-center rounded-lg">
							{getConnectorIcon(EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR, "h-6 w-6")}
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Google Calendar</h1>
							<p className="text-muted-foreground">
								Connect your Google Calendar to search events.
							</p>
						</div>
					</div>
				</div>

				{/* OAuth Connection Card */}
				{!doesConnectorExist ? (
					<Card>
						<CardHeader>
							<CardTitle>Connect Your Google Account</CardTitle>
							<CardDescription>
								Connect your Google account to access your calendar events. We'll only request
								read-only access to your calendars.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="flex items-center space-x-2 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Read-only access to your calendar events</span>
							</div>
							<div className="flex items-center space-x-2 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Access works even when you're offline</span>
							</div>
							<div className="flex items-center space-x-2 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>You can disconnect anytime</span>
							</div>
						</CardContent>
						<CardFooter className="flex justify-between">
							<Button
								type="button"
								variant="outline"
								onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}
							>
								Cancel
							</Button>
							<Button onClick={handleConnectGoogle} disabled={isConnecting}>
								{isConnecting ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Connecting...
									</>
								) : (
									<>
										<ExternalLink className="mr-2 h-4 w-4" />
										Connect Your Google Account
									</>
								)}
							</Button>
						</CardFooter>
					</Card>
				) : (
					/* Configuration Form Card */
					<Card>
						<CardHeader>
							<CardTitle>✅ Your Google calendar is successfully connected!</CardTitle>
						</CardHeader>
					</Card>
				)}

				{/* Help Section */}
				{!doesConnectorExist && (
					<Card className="mt-6">
						<CardHeader>
							<CardTitle className="text-lg">How It Works</CardTitle>
						</CardHeader>
						<CardContent className="space-y-4">
							<div>
								<h4 className="font-medium mb-2">1. Connect Your Account</h4>
								<p className="text-sm text-muted-foreground">
									Click "Connect Your Google Account" to start the secure OAuth process. You'll be
									redirected to Google to sign in.
								</p>
							</div>
							<div>
								<h4 className="font-medium mb-2">2. Grant Permissions</h4>
								<p className="text-sm text-muted-foreground">
									Google will ask for permission to read your calendar events. We only request
									read-only access to keep your data safe.
								</p>
							</div>
						</CardContent>
					</Card>
				)}
			</motion.div>
		</div>
	);
}
