"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const bookstackConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	base_url: z
		.string()
		.url({
			message: "Please enter a valid BookStack URL (e.g., https://docs.example.com)",
		}),
	token_id: z.string().min(10, {
		message: "BookStack Token ID is required.",
	}),
	token_secret: z.string().min(10, {
		message: "BookStack Token Secret is required.",
	}),
});

// Define the type for the form values
type BookStackConnectorFormValues = z.infer<typeof bookstackConnectorFormSchema>;

export default function BookStackConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<BookStackConnectorFormValues>({
		resolver: zodResolver(bookstackConnectorFormSchema),
		defaultValues: {
			name: "BookStack Connector",
			base_url: "",
			token_id: "",
			token_secret: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: BookStackConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.BOOKSTACK_CONNECTOR,
					config: {
						BOOKSTACK_BASE_URL: values.base_url,
						BOOKSTACK_TOKEN_ID: values.token_id,
						BOOKSTACK_TOKEN_SECRET: values.token_secret,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("BookStack connector created successfully!");

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
		<div className="container mx-auto py-8 max-w-3xl">
			<Button
				variant="ghost"
				className="mb-6"
				onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}
			>
				<ArrowLeft className="mr-2 h-4 w-4" />
				Back to Connectors
			</Button>

			{/* Header */}
			<div className="mb-8">
				<div className="flex items-center gap-4">
					<div className="flex h-12 w-12 items-center justify-center rounded-lg">
						{getConnectorIcon(EnumConnectorName.BOOKSTACK_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect BookStack</h1>
						<p className="text-muted-foreground">
							Connect your BookStack instance to search wiki pages.
						</p>
					</div>
				</div>
			</div>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Tabs defaultValue="connect" className="w-full">
					<TabsList className="grid w-full grid-cols-2 mb-6">
						<TabsTrigger value="connect">Connect</TabsTrigger>
						<TabsTrigger value="documentation">Documentation</TabsTrigger>
					</TabsList>

					<TabsContent value="connect">
						<Card>
							<CardHeader>
								<CardTitle>Connect to BookStack</CardTitle>
								<CardDescription>
									Connect your BookStack instance to index pages from your wiki.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<Alert>
									<Info className="h-4 w-4" />
									<AlertDescription>
										You'll need to create an API token from your BookStack instance.
										Go to <strong>Edit Profile → API Tokens → Create Token</strong>
									</AlertDescription>
								</Alert>

								<Form {...form}>
									<form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
										<FormField
											control={form.control}
											name="name"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Connector Name</FormLabel>
													<FormControl>
														<Input placeholder="My BookStack Connector" {...field} />
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
											name="base_url"
											render={({ field }) => (
												<FormItem>
													<FormLabel>BookStack Instance URL</FormLabel>
													<FormControl>
														<Input placeholder="https://docs.example.com" {...field} />
													</FormControl>
													<FormDescription>
														Your BookStack instance URL (e.g., https://wiki.yourcompany.com)
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="token_id"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Token ID</FormLabel>
													<FormControl>
														<Input placeholder="Your BookStack Token ID" {...field} />
													</FormControl>
													<FormDescription>
														The Token ID from your BookStack API token.
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="token_secret"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Token Secret</FormLabel>
													<FormControl>
														<Input
															type="password"
															placeholder="Your BookStack Token Secret"
															{...field}
														/>
													</FormControl>
													<FormDescription>
														Your Token Secret will be encrypted and stored securely.
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<div className="flex justify-end">
											<Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
												{isSubmitting ? (
													<>
														<Loader2 className="mr-2 h-4 w-4 animate-spin" />
														Connecting...
													</>
												) : (
													<>
														<Check className="mr-2 h-4 w-4" />
														Connect BookStack
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card>
							<CardHeader>
								<CardTitle>BookStack Integration Guide</CardTitle>
								<CardDescription>
									Learn how to set up and use the BookStack connector.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-lg font-semibold mb-3">What gets indexed?</h3>
									<ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
										<li>All pages from your BookStack instance</li>
										<li>Page content in Markdown format</li>
										<li>Page titles and metadata</li>
										<li>Book and chapter hierarchy information</li>
									</ul>
								</div>

								<div>
									<h3 className="text-lg font-semibold mb-3">Setup Instructions</h3>
									<ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
										<li>Log in to your BookStack instance</li>
										<li>Click on your profile icon → Edit Profile</li>
										<li>Navigate to the "API Tokens" tab</li>
										<li>Click "Create Token" and give it a name</li>
										<li>Copy both the Token ID and Token Secret</li>
										<li>Paste them in the form above</li>
									</ol>
								</div>

								<div>
									<h3 className="text-lg font-semibold mb-3">Permissions Required</h3>
									<ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
										<li>Your user account must have "Access System API" permission</li>
										<li>Read access to books and pages you want to index</li>
										<li>The connector will only index content your account can view</li>
									</ul>
								</div>

								<Alert>
									<Info className="h-4 w-4" />
									<AlertDescription>
										BookStack API has a rate limit of 180 requests per minute. The connector
										automatically handles rate limiting to ensure reliable indexing.
									</AlertDescription>
								</Alert>
							</CardContent>
						</Card>
					</TabsContent>
				</Tabs>
			</motion.div>
		</div>
	);
}
