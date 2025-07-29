"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
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

import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";

// Define the form schema with Zod
const confluenceConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	base_url: z
		.string()
		.url({
			message: "Please enter a valid Confluence URL (e.g., https://yourcompany.atlassian.net)",
		})
		.refine(
			(url) => {
				return url.includes("atlassian.net") || url.includes("confluence");
			},
			{
				message: "Please enter a valid Confluence instance URL",
			}
		),
	email: z.string().email({
		message: "Please enter a valid email address.",
	}),
	api_token: z.string().min(10, {
		message: "Confluence API Token is required and must be valid.",
	}),
});

// Define the type for the form values
type ConfluenceConnectorFormValues = z.infer<typeof confluenceConnectorFormSchema>;

export default function ConfluenceConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<ConfluenceConnectorFormValues>({
		resolver: zodResolver(confluenceConnectorFormSchema),
		defaultValues: {
			name: "Confluence Connector",
			base_url: "",
			email: "",
			api_token: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: ConfluenceConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector({
				name: values.name,
				connector_type: "CONFLUENCE_CONNECTOR",
				config: {
					CONFLUENCE_BASE_URL: values.base_url,
					CONFLUENCE_EMAIL: values.email,
					CONFLUENCE_API_TOKEN: values.api_token,
				},
				is_indexable: true,
				last_indexed_at: null,
			});

			toast.success("Confluence connector created successfully!");

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
								<CardTitle>Connect to Confluence</CardTitle>
								<CardDescription>
									Connect your Confluence instance to index pages and comments from your spaces.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<Alert>
									<Info className="h-4 w-4" />
									<AlertDescription>
										You'll need to create an API token from your{" "}
										<a
											href="https://id.atlassian.com/manage-profile/security/api-tokens"
											target="_blank"
											rel="noopener noreferrer"
											className="font-medium underline underline-offset-4"
										>
											Atlassian Account Settings
										</a>
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
														<Input placeholder="My Confluence Connector" {...field} />
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
													<FormLabel>Confluence Instance URL</FormLabel>
													<FormControl>
														<Input placeholder="https://yourcompany.atlassian.net" {...field} />
													</FormControl>
													<FormDescription>
														Your Confluence instance URL. For Atlassian Cloud, this is typically
														https://yourcompany.atlassian.net
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="email"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Email Address</FormLabel>
													<FormControl>
														<Input type="email" placeholder="your.email@company.com" {...field} />
													</FormControl>
													<FormDescription>Your Atlassian account email address.</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="api_token"
											render={({ field }) => (
												<FormItem>
													<FormLabel>API Token</FormLabel>
													<FormControl>
														<Input
															type="password"
															placeholder="Your Confluence API Token"
															{...field}
														/>
													</FormControl>
													<FormDescription>
														Your Confluence API Token will be encrypted and stored securely.
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
														Connect Confluence
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
								<CardTitle>Confluence Integration Guide</CardTitle>
								<CardDescription>
									Learn how to set up and use the Confluence connector.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-lg font-semibold mb-3">What gets indexed?</h3>
									<ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
										<li>All pages from accessible spaces</li>
										<li>Page content and metadata</li>
										<li>Comments on pages (both footer and inline comments)</li>
										<li>Page titles and descriptions</li>
									</ul>
								</div>

								<div>
									<h3 className="text-lg font-semibold mb-3">Setup Instructions</h3>
									<ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
										<li>Go to your Atlassian Account Settings</li>
										<li>Navigate to Security → API tokens</li>
										<li>Create a new API token with appropriate permissions</li>
										<li>Copy the token and paste it in the form above</li>
										<li>Ensure your account has read access to the spaces you want to index</li>
									</ol>
								</div>

								<div>
									<h3 className="text-lg font-semibold mb-3">Permissions Required</h3>
									<ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
										<li>Read access to Confluence spaces</li>
										<li>View pages and comments</li>
										<li>Access to space metadata</li>
									</ul>
								</div>

								<Alert>
									<Info className="h-4 w-4" />
									<AlertDescription>
										The connector will only index content that your account has permission to view.
										Make sure your API token has the necessary permissions for the spaces you want
										to index.
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
