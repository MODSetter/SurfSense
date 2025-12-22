"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const jiraConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	base_url: z
		.string()
		.url({
			message: "Please enter a valid Jira URL (e.g., https://yourcompany.atlassian.net)",
		})
		.refine(
			(url) => {
				return url.includes("atlassian.net") || url.includes("jira");
			},
			{
				message: "Please enter a valid Jira instance URL",
			}
		),
	email: z.string().email({
		message: "Please enter a valid email address.",
	}),
	api_token: z.string().min(10, {
		message: "Jira API Token is required and must be valid.",
	}),
});

// Define the type for the form values
type JiraConnectorFormValues = z.infer<typeof jiraConnectorFormSchema>;

export default function JiraConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<JiraConnectorFormValues>({
		resolver: zodResolver(jiraConnectorFormSchema),
		defaultValues: {
			name: "Jira Connector",
			base_url: "",
			email: "",
			api_token: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: JiraConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.JIRA_CONNECTOR,
					config: {
						JIRA_BASE_URL: values.base_url,
						JIRA_EMAIL: values.email,
						JIRA_API_TOKEN: values.api_token,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Jira connector created successfully!");

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
						{getConnectorIcon(EnumConnectorName.JIRA_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Jira</h1>
						<p className="text-muted-foreground">
							Connect your Jira instance to search issues and tickets.
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
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Connect Jira Instance</CardTitle>
								<CardDescription>
									Integrate with Jira to search and retrieve information from your issues, tickets,
									and comments. This connector can index your Jira content for search.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Alert className="mb-6 bg-muted">
									<Info className="h-4 w-4" />
									<AlertTitle>Jira Personal Access Token Required</AlertTitle>
									<AlertDescription>
										You'll need a Jira Personal Access Token to use this connector. You can create
										one from{" "}
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
														<Input placeholder="My Jira Connector" {...field} />
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
													<FormLabel>Jira Instance URL</FormLabel>
													<FormControl>
														<Input placeholder="https://yourcompany.atlassian.net" {...field} />
													</FormControl>
													<FormDescription>
														Your Jira instance URL. For Atlassian Cloud, this is typically
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
														<Input type="password" placeholder="Your Jira API Token" {...field} />
													</FormControl>
													<FormDescription>
														Your Jira API Token will be encrypted and stored securely.
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
														Connect Jira
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Jira integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through all your Jira issues and tickets</li>
									<li>Access issue descriptions, comments, and full discussion threads</li>
									<li>Connect your team's project management directly to your search space</li>
									<li>Keep your search results up-to-date with latest Jira content</li>
									<li>Index your Jira issues for enhanced search capabilities</li>
									<li>Search by issue keys, status, priority, and assignee information</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Jira Connector Documentation</CardTitle>
								<CardDescription>
									Learn how to set up and use the Jira connector to index your project management
									data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Jira connector uses the Jira REST API with Basic Authentication to fetch all
										issues and comments that your account has access to within your Jira instance.
									</p>
									<ul className="mt-2 list-disc pl-5 text-muted-foreground">
										<li>
											For follow up indexing runs, the connector retrieves issues and comments that
											have been updated since the last indexing attempt.
										</li>
										<li>
											Indexing is configured to run periodically, so updates should appear in your
											search results within minutes.
										</li>
									</ul>
								</div>

								<Accordion type="single" collapsible className="w-full">
									<AccordionItem value="authorization">
										<AccordionTrigger className="text-lg font-medium">
											Authorization
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>Read-Only Access is Sufficient</AlertTitle>
												<AlertDescription>
													You only need read access for this connector to work. The API Token will
													only be used to read your Jira data.
												</AlertDescription>
											</Alert>

											<div className="space-y-6">
												<div>
													<h4 className="font-medium mb-2">Step 1: Create an API Token</h4>
													<ol className="list-decimal pl-5 space-y-3">
														<li>Log in to your Atlassian account</li>
														<li>
															Navigate to{" "}
															<a
																href="https://id.atlassian.com/manage-profile/security/api-tokens"
																target="_blank"
																rel="noopener noreferrer"
																className="font-medium underline underline-offset-4"
															>
																https://id.atlassian.com/manage-profile/security/api-tokens
															</a>
														</li>
														<li>
															Click <strong>Create API token</strong>
														</li>
														<li>Enter a label for your token (like "SurfSense Connector")</li>
														<li>
															Click <strong>Create</strong>
														</li>
														<li>Copy the generated token as it will only be shown once</li>
													</ol>
												</div>

												<div>
													<h4 className="font-medium mb-2">Step 2: Grant necessary access</h4>
													<p className="text-muted-foreground mb-3">
														The API Token will have access to all projects and issues that your user
														account can see. Make sure your account has appropriate permissions for
														the projects you want to index.
													</p>
													<Alert className="bg-muted">
														<Info className="h-4 w-4" />
														<AlertTitle>Data Privacy</AlertTitle>
														<AlertDescription>
															Only issues, comments, and basic metadata will be indexed. Jira
															attachments and linked files are not indexed by this connector.
														</AlertDescription>
													</Alert>
												</div>
											</div>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="indexing">
										<AccordionTrigger className="text-lg font-medium">Indexing</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<ol className="list-decimal pl-5 space-y-3">
												<li>
													Navigate to the Connector Dashboard and select the <strong>Jira</strong>{" "}
													Connector.
												</li>
												<li>
													Enter your <strong>Jira Instance URL</strong> (e.g.,
													https://yourcompany.atlassian.net)
												</li>
												<li>
													Place your <strong>Personal Access Token</strong> in the form field.
												</li>
												<li>
													Click <strong>Connect</strong> to establish the connection.
												</li>
												<li>Once connected, your Jira issues will be indexed automatically.</li>
											</ol>

											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>What Gets Indexed</AlertTitle>
												<AlertDescription>
													<p className="mb-2">The Jira connector indexes the following data:</p>
													<ul className="list-disc pl-5">
														<li>Issue keys and summaries (e.g., PROJ-123)</li>
														<li>Issue descriptions</li>
														<li>Issue comments and discussion threads</li>
														<li>Issue status, priority, and type information</li>
														<li>Assignee and reporter information</li>
														<li>Project information</li>
													</ul>
												</AlertDescription>
											</Alert>
										</AccordionContent>
									</AccordionItem>
								</Accordion>
							</CardContent>
						</Card>
					</TabsContent>
				</Tabs>
			</motion.div>
		</div>
	);
}
