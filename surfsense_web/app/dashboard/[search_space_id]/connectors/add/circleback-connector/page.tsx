"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAtomValue } from "jotai";
import { ArrowLeft, Check, Copy, ExternalLink, Loader2, Webhook } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
import { createConnectorMutationAtom } from "@/atoms/connectors/connector-mutation.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

// Define the form schema with Zod
const circlebackConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
});

// Define the type for the form values
type CirclebackConnectorFormValues = z.infer<typeof circlebackConnectorFormSchema>;

export default function CirclebackConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [doesConnectorExist, setDoesConnectorExist] = useState(false);
	const [copied, setCopied] = useState(false);

	const { data: connectors } = useAtomValue(connectorsAtom);
	const { mutateAsync: createConnector } = useAtomValue(createConnectorMutationAtom);

	// Construct the webhook URL
	const apiBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
	const webhookUrl = `${apiBaseUrl}/api/v1/webhooks/circleback/${searchSpaceId}`;

	// Initialize the form
	const form = useForm<CirclebackConnectorFormValues>({
		resolver: zodResolver(circlebackConnectorFormSchema),
		defaultValues: {
			name: "Circleback Meetings",
		},
	});

	const { refetch: fetchConnectors } = useAtomValue(connectorsAtom);

	useEffect(() => {
		fetchConnectors().then((data) => {
			const connectors = data.data || [];
			const connector = connectors.find(
				(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.CIRCLEBACK_CONNECTOR
			);
			if (connector) {
				setDoesConnectorExist(true);
			}
		});
	}, []);

	// Copy webhook URL to clipboard
	const copyToClipboard = async () => {
		try {
			await navigator.clipboard.writeText(webhookUrl);
			setCopied(true);
			toast.success("Webhook URL copied to clipboard!");
			setTimeout(() => setCopied(false), 2000);
		} catch {
			toast.error("Failed to copy to clipboard");
		}
	};

	// Handle form submission
	const onSubmit = async (values: CirclebackConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector({
				data: {
					name: values.name,
					connector_type: EnumConnectorName.CIRCLEBACK_CONNECTOR,
					config: {
						webhook_url: webhookUrl,
					},
					is_indexable: false, // Webhooks push data, not indexed
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				queryParams: {
					search_space_id: searchSpaceId,
				},
			});

			toast.success("Circleback connector created successfully!");

			// Navigate back to connectors page
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		} catch (error) {
			console.error("Error creating connector:", error);
			toast.error(error instanceof Error ? error.message : "Failed to create connector");
		} finally {
			setIsSubmitting(false);
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
							{getConnectorIcon(EnumConnectorName.CIRCLEBACK_CONNECTOR, "h-6 w-6")}
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Circleback</h1>
							<p className="text-muted-foreground">
								Receive meeting notes and transcripts via webhook.
							</p>
						</div>
					</div>
				</div>

				{/* Connection Card */}
				{!doesConnectorExist ? (
					<>
						<Card className="mb-6">
							<CardHeader>
								<CardTitle>Webhook Configuration</CardTitle>
								<CardDescription>
									Use this webhook URL in your Circleback automation to send meeting data to
									SurfSense.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<label className="text-sm font-medium">Webhook URL</label>
									<div className="flex gap-2">
										<Input value={webhookUrl} readOnly className="font-mono text-sm" />
										<Button
											type="button"
											variant="outline"
											size="icon"
											onClick={copyToClipboard}
											className="shrink-0"
										>
											{copied ? (
												<Check className="h-4 w-4 text-green-500" />
											) : (
												<Copy className="h-4 w-4" />
											)}
										</Button>
									</div>
									<p className="text-xs text-muted-foreground">
										Copy this URL and paste it in your Circleback automation settings.
									</p>
								</div>

								<Alert>
									<Webhook className="h-4 w-4" />
									<AlertTitle>How it works</AlertTitle>
									<AlertDescription>
										When you configure this webhook in Circleback, it will automatically send
										meeting notes, transcripts, and action items to SurfSense after each meeting.
									</AlertDescription>
								</Alert>
							</CardContent>
						</Card>

						<Card>
							<CardHeader>
								<CardTitle>Create Connector</CardTitle>
								<CardDescription>
									Register the Circleback connector to track incoming meeting data.
								</CardDescription>
							</CardHeader>
							<Form {...form}>
								<form onSubmit={form.handleSubmit(onSubmit)}>
									<CardContent className="space-y-4">
										<FormField
											control={form.control}
											name="name"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Connector Name</FormLabel>
													<FormControl>
														<Input placeholder="My Circleback Meetings" {...field} />
													</FormControl>
													<FormDescription>
														A friendly name to identify this connector.
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<div className="space-y-2 pt-2">
											<div className="flex items-center space-x-2 text-sm text-muted-foreground">
												<Check className="h-4 w-4 text-green-500" />
												<span>Automatic meeting notes import</span>
											</div>
											<div className="flex items-center space-x-2 text-sm text-muted-foreground">
												<Check className="h-4 w-4 text-green-500" />
												<span>Full transcripts with speaker identification</span>
											</div>
											<div className="flex items-center space-x-2 text-sm text-muted-foreground">
												<Check className="h-4 w-4 text-green-500" />
												<span>Action items and insights extraction</span>
											</div>
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
										<Button type="submit" disabled={isSubmitting}>
											{isSubmitting ? (
												<>
													<Loader2 className="mr-2 h-4 w-4 animate-spin" />
													Creating...
												</>
											) : (
												<>
													<Webhook className="mr-2 h-4 w-4" />
													Create Connector
												</>
											)}
										</Button>
									</CardFooter>
								</form>
							</Form>
						</Card>
					</>
				) : (
					/* Success Card */
					<Card>
						<CardHeader>
							<CardTitle>✅ Circleback connector is active!</CardTitle>
							<CardDescription>
								Your Circleback meetings will be automatically imported to this search space.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="space-y-2">
								<label className="text-sm font-medium">Webhook URL</label>
								<div className="flex gap-2">
									<Input value={webhookUrl} readOnly className="font-mono text-sm" />
									<Button
										type="button"
										variant="outline"
										size="icon"
										onClick={copyToClipboard}
										className="shrink-0"
									>
										{copied ? (
											<Check className="h-4 w-4 text-green-500" />
										) : (
											<Copy className="h-4 w-4" />
										)}
									</Button>
								</div>
							</div>
						</CardContent>
					</Card>
				)}

				{/* Help Section */}
				<Card className="mt-6">
					<CardHeader>
						<CardTitle className="text-lg">Setup Instructions</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div>
							<h4 className="font-medium mb-2">1. Copy the Webhook URL</h4>
							<p className="text-sm text-muted-foreground">
								Copy the webhook URL shown above. You'll need this for the next step.
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">2. Open Circleback Automations</h4>
							<p className="text-sm text-muted-foreground">
								Go to{" "}
								<a
									href="https://app.circleback.ai/automations"
									target="_blank"
									rel="noopener noreferrer"
									className="text-primary hover:underline inline-flex items-center gap-1"
								>
									Circleback Automations
									<ExternalLink className="h-3 w-3" />
								</a>{" "}
								and click "Create automation".
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">3. Configure the Webhook</h4>
							<p className="text-sm text-muted-foreground">
								Set your automation conditions, then select "Send webhook request" and paste the
								webhook URL.
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">4. Select Meeting Outcomes</h4>
							<p className="text-sm text-muted-foreground">
								Choose which meeting data to include: notes, transcript, action items, and
								insights.
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">5. Create & Test</h4>
							<p className="text-sm text-muted-foreground">
								Give your automation a name and create it. You can send a test request to verify
								the integration works.
							</p>
						</div>
					</CardContent>
				</Card>
			</motion.div>
		</div>
	);
}

