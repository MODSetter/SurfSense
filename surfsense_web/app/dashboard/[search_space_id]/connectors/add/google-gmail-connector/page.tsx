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

export default function GoogleGmailConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isConnecting, setIsConnecting] = useState(false);
	const [doesConnectorExist, setDoesConnectorExist] = useState(false);

	const { fetchConnectors } = useSearchSourceConnectors(true, parseInt(searchSpaceId));

	useEffect(() => {
		fetchConnectors(parseInt(searchSpaceId)).then((data) => {
			const connector = data.find(
				(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.GOOGLE_GMAIL_CONNECTOR
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
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/auth/google/gmail/connector/add/?space_id=${searchSpaceId}`,
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
			toast.error("Failed to connect to Google Gmail");
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
							{getConnectorIcon(EnumConnectorName.GOOGLE_GMAIL_CONNECTOR, "h-6 w-6")}
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Google Gmail</h1>
							<p className="text-muted-foreground">
								Connect your Gmail account to search through your emails
							</p>
						</div>
					</div>
				</div>

				{/* Connection Card */}
				{!doesConnectorExist ? (
					<Card>
						<CardHeader>
							<CardTitle>Connect Your Gmail Account</CardTitle>
							<CardDescription>
								Securely connect your Gmail account to enable email search within SurfSense. We'll
								only access your emails with read-only permissions.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Read-only access to your emails</span>
							</div>
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Search through email content and metadata</span>
							</div>
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Secure OAuth 2.0 authentication</span>
							</div>
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
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
							<CardTitle>✅ Your Gmail is successfully connected!</CardTitle>
						</CardHeader>
					</Card>
				)}

				{/* Information Card */}
				<Card className="mt-6">
					<CardHeader>
						<CardTitle>What data will be indexed?</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="space-y-2">
							<h4 className="font-medium">Email Content</h4>
							<p className="text-sm text-muted-foreground">
								We'll index the content of your emails including subject lines, sender information,
								and message body text to make them searchable.
							</p>
						</div>
						<div className="space-y-2">
							<h4 className="font-medium">Email Metadata</h4>
							<p className="text-sm text-muted-foreground">
								Information like sender, recipient, date, and labels will be indexed to provide
								better search context and filtering options.
							</p>
						</div>
						<div className="space-y-2">
							<h4 className="font-medium">Privacy & Security</h4>
							<p className="text-sm text-muted-foreground">
								Your emails are processed securely and stored with encryption. We only access emails
								with read-only permissions and never modify or send emails on your behalf.
							</p>
						</div>
					</CardContent>
				</Card>
			</motion.div>
		</div>
	);
}
