"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Key, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
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
import {
	type SearchSourceConnector,
	useSearchSourceConnectors,
} from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const lumaConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_key: z.string().min(10, {
		message: "API key is required and must be valid.",
	}),
});

// Define the type for the form values
type LumaConnectorFormValues = z.infer<typeof lumaConnectorFormSchema>;

export default function LumaConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [doesConnectorExist, setDoesConnectorExist] = useState(false);

	const { fetchConnectors, createConnector } = useSearchSourceConnectors(
		true,
		parseInt(searchSpaceId)
	);

	// Initialize the form
	const form = useForm<LumaConnectorFormValues>({
		resolver: zodResolver(lumaConnectorFormSchema),
		defaultValues: {
			name: "Luma Events",
			api_key: "",
		},
	});

	useEffect(() => {
		fetchConnectors(parseInt(searchSpaceId))
			.then((data) => {
				if (data && Array.isArray(data)) {
					const connector = data.find(
						(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.LUMA_CONNECTOR
					);
					if (connector) {
						setDoesConnectorExist(true);
					}
				}
			})
			.catch((error) => {
				console.error("Error fetching connectors:", error);
			});
	}, [fetchConnectors, searchSpaceId]);

	// Handle form submission
	const onSubmit = async (values: LumaConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.LUMA_CONNECTOR,
					config: {
						LUMA_API_KEY: values.api_key,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Luma connector created successfully!");

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
							{getConnectorIcon(EnumConnectorName.LUMA_CONNECTOR, "h-6 w-6")}
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Luma</h1>
							<p className="text-muted-foreground">Connect your Luma account to search events.</p>
						</div>
					</div>
				</div>

				{/* Connection Card */}
				{!doesConnectorExist ? (
					<Card>
						<CardHeader>
							<CardTitle>Connect Your Luma Account</CardTitle>
							<CardDescription>
								Enter your Luma API key to connect your account. We'll use this to access your
								events in read-only mode.
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
													<Input placeholder="My Luma Events" {...field} />
												</FormControl>
												<FormDescription>
													A friendly name to identify this connector.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									<FormField
										control={form.control}
										name="api_key"
										render={({ field }) => (
											<FormItem>
												<FormLabel>API Key</FormLabel>
												<FormControl>
													<Input type="password" placeholder="Enter your Luma API key" {...field} />
												</FormControl>
												<FormDescription>
													Your API key will be encrypted and stored securely.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									<div className="space-y-2 pt-2">
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>Read-only access to your Luma events</span>
										</div>
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>Access works even when you're offline</span>
										</div>
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>You can disconnect anytime</span>
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
												Connecting...
											</>
										) : (
											<>
												<Key className="mr-2 h-4 w-4" />
												Connect Luma
											</>
										)}
									</Button>
								</CardFooter>
							</form>
						</Form>
					</Card>
				) : (
					/* Success Card */
					<Card>
						<CardHeader>
							<CardTitle>✅ Your Luma account is successfully connected!</CardTitle>
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
								<h4 className="font-medium mb-2">1. Get Your API Key</h4>
								<p className="text-sm text-muted-foreground">
									Log into your Luma account and navigate to your account settings to generate an
									API key.
								</p>
							</div>
							<div>
								<h4 className="font-medium mb-2">2. Enter Your API Key</h4>
								<p className="text-sm text-muted-foreground">
									Paste your API key in the field above. We'll use this to securely access your
									events with read-only permissions.
								</p>
							</div>
						</CardContent>
					</Card>
				)}
			</motion.div>
		</div>
	);
}
