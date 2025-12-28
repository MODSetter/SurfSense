"use client";

import { ArrowLeft, Check, ExternalLink, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
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
import { authenticatedFetch } from "@/lib/auth-utils";

export default function GoogleDriveConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchParams = useSearchParams();
	const searchSpaceId = params.search_space_id as string;
	
	const [isConnecting, setIsConnecting] = useState(false);
	const [doesConnectorExist, setDoesConnectorExist] = useState(false);

	const { fetchConnectors } = useSearchSourceConnectors(true, Number.parseInt(searchSpaceId));

	// Check if connector exists and handle OAuth success
	useEffect(() => {
		const success = searchParams.get("success");
		
		fetchConnectors(Number.parseInt(searchSpaceId)).then((data) => {
			const driveConnector = data.find(
				(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.GOOGLE_DRIVE_CONNECTOR
			);
			
			if (driveConnector) {
				setDoesConnectorExist(true);
				
				// If just connected, show success and redirect
				if (success === "true") {
					toast.success("Google Drive connected successfully!");
					setTimeout(() => {
						router.push(`/dashboard/${searchSpaceId}/connectors`);
					}, 1500);
				}
			}
		});
	}, [searchParams, fetchConnectors, searchSpaceId, router]);

	const handleConnectGoogle = async () => {
		try {
			setIsConnecting(true);
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/auth/google/drive/connector/add/?space_id=${searchSpaceId}`,
				{ method: "GET" }
			);

			if (!response.ok) {
				throw new Error("Failed to initiate Google OAuth");
			}

			const data = await response.json();
			window.location.href = data.auth_url;
		} catch (error) {
			console.error("Error connecting to Google:", error);
			toast.error("Failed to connect to Google Drive");
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
							{getConnectorIcon(EnumConnectorName.GOOGLE_DRIVE_CONNECTOR, "h-6 w-6")}
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Google Drive</h1>
							<p className="text-muted-foreground">
								Securely connect your Google Drive account
							</p>
						</div>
					</div>
				</div>

				{/* Connection Card */}
				{!doesConnectorExist ? (
					<Card>
						<CardHeader>
							<CardTitle>Connect Your Google Account</CardTitle>
							<CardDescription>
								Authorize read-only access to your Google Drive. You'll select which folder to
								index when you start indexing.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Read-only access to your Drive files</span>
							</div>
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Index documents, spreadsheets, presentations, PDFs & more</span>
							</div>
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Automatic updates with change tracking</span>
							</div>
							<div className="flex items-center gap-3 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Secure OAuth 2.0 authentication</span>
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
										Connect Google Drive
									</>
								)}
							</Button>
						</CardFooter>
					</Card>
				) : (
					<Card>
						<CardHeader>
							<CardTitle>✅ Already Connected</CardTitle>
							<CardDescription>
								Your Google Drive connector is already set up. Go to the connectors page to
								start indexing.
							</CardDescription>
						</CardHeader>
						<CardFooter>
							<Button onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors`)}>
								Go to Connectors
							</Button>
						</CardFooter>
					</Card>
				)}

				{/* Information Card */}
				<Card className="mt-6">
					<CardHeader>
						<CardTitle>How Google Drive Integration Works</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="space-y-2">
							<h4 className="font-medium">1️⃣ Connect Your Account</h4>
							<p className="text-sm text-muted-foreground">
								First, securely connect your Google Drive account using OAuth 2.0. We only
								request read-only access.
							</p>
						</div>
						<div className="space-y-2">
							<h4 className="font-medium">2️⃣ Select Folder to Index</h4>
							<p className="text-sm text-muted-foreground">
								When you're ready to index, go to the connectors page and click "Index". You'll
								choose which folder to process.
							</p>
						</div>
						<div className="space-y-2">
							<h4 className="font-medium">3️⃣ Automatic Change Detection</h4>
							<p className="text-sm text-muted-foreground">
								We use Google Drive's change tracking API to detect when files are modified,
								added, or deleted. Only changed files are re-indexed.
							</p>
						</div>
						<div className="space-y-2">
							<h4 className="font-medium">📄 Comprehensive File Support</h4>
							<p className="text-sm text-muted-foreground">
								Supports Google Workspace files (Docs, Sheets, Slides), Microsoft Office
								documents, PDFs, text files, images (with OCR), and more.
							</p>
						</div>
					</CardContent>
				</Card>
			</motion.div>
		</div>
	);
}
