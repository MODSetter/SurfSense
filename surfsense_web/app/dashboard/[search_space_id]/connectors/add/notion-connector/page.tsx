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
const notionConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	integration_token: z.string().min(10, {
		message: "Notion Integration Token is required and must be valid.",
	}),
});

// Define the type for the form values
type NotionConnectorFormValues = z.infer<typeof notionConnectorFormSchema>;

export default function NotionConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<NotionConnectorFormValues>({
		resolver: zodResolver(notionConnectorFormSchema),
		defaultValues: {
			name: "Notion Connector",
			integration_token: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: NotionConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.NOTION_CONNECTOR,
					config: {
						NOTION_INTEGRATION_TOKEN: values.integration_token,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Notion connector created successfully!");

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
						{getConnectorIcon(EnumConnectorName.NOTION_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Notion</h1>
						<p className="text-muted-foreground">
							Connect your Notion workspace to search pages and databases.
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
								<CardTitle className="text-2xl font-bold">Connect Notion Workspace</CardTitle>
								<CardDescription>
									Integrate with Notion to search and retrieve information from your workspace pages
									and databases. This connector can index your Notion content for search.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Alert className="mb-6 bg-muted">
									<Info className="h-4 w-4" />
									<AlertTitle>Notion Integration Token Required</AlertTitle>
									<AlertDescription>
										You'll need a Notion Integration Token to use this connector. You can create a
										Notion integration and get the token from{" "}
										<a
											href="https://www.notion.so/my-integrations"
											target="_blank"
											rel="noopener noreferrer"
											className="font-medium underline underline-offset-4"
										>
											Notion Integrations Dashboard
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
														<Input placeholder="My Notion Connector" {...field} />
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
											name="integration_token"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Notion Integration Token</FormLabel>
													<FormControl>
														<Input type="password" placeholder="ntn_.." {...field} />
													</FormControl>
													<FormDescription>
														Your Notion Integration Token will be encrypted and stored securely. It
														typically starts with "ntn_".
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
														Connect Notion
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Notion integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through your Notion pages and databases</li>
									<li>Access documents, wikis, and knowledge bases</li>
									<li>Connect your team's knowledge directly to your search space</li>
									<li>Keep your search results up-to-date with latest Notion content</li>
									<li>Index your Notion documents for enhanced search capabilities</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Notion Connector Documentation</CardTitle>
								<CardDescription>
									Learn how to set up and use the Notion connector to index your workspace data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Notion connector uses the Notion search API to fetch all pages that the
										connector has access to within a workspace.
									</p>
									<ul className="mt-2 list-disc pl-5 text-muted-foreground">
										<li>
											For follow up indexing runs, the connector only retrieves pages that have been
											updated since the last indexing attempt.
										</li>
										<li>
											Indexing is configured to run every <strong>10 minutes</strong>, so page
											updates should appear within 10 minutes.
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
												<AlertTitle>No Admin Access Required</AlertTitle>
												<AlertDescription>
													There's no requirement to be an Admin to share information with an
													integration. Any member can share pages and databases with it.
												</AlertDescription>
											</Alert>

											<div className="space-y-6">
												<div>
													<h4 className="font-medium mb-2">Step 1: Create an integration</h4>
													<ol className="list-decimal pl-5 space-y-3">
														<li>
															Visit{" "}
															<a
																href="https://www.notion.com/my-integrations"
																target="_blank"
																rel="noopener noreferrer"
																className="font-medium underline underline-offset-4"
															>
																https://www.notion.com/my-integrations
															</a>{" "}
															in your browser.
														</li>
														<li>
															Click the <strong>+ New integration</strong> button.
														</li>
														<li>
															Name the integration (something like "Search Connector" could work).
														</li>
														<li>Select "Read content" as the only capability required.</li>
														<li>
															Click <strong>Submit</strong> to create the integration.
														</li>
														<li>
															On the next page, you'll find your Notion integration token. Make a
															copy of it as you'll need it to configure the connector.
														</li>
													</ol>
												</div>

												<div>
													<h4 className="font-medium mb-2">
														Step 2: Share pages/databases with your integration
													</h4>
													<p className="text-muted-foreground mb-3">
														To keep your information secure, integrations don't have access to any
														pages or databases in the workspace at first. You must share specific
														pages with an integration in order for the connector to access those
														pages.
													</p>
													<ol className="list-decimal pl-5 space-y-3">
														<li>Go to the page/database in your workspace.</li>
														<li>
															Click the <code>•••</code> on the top right corner of the page.
														</li>
														<li>
															Scroll to the bottom of the pop-up and click{" "}
															<strong>Add connections</strong>.
														</li>
														<li>
															Search for and select the new integration in the{" "}
															<code>Search for connections...</code> menu.
														</li>
														<li>
															<strong>Important:</strong>
															<ul className="list-disc pl-5 mt-1">
																<li>
																	If you've added a page, all child pages also become accessible.
																</li>
																<li>
																	If you've added a database, all rows (and their children) become
																	accessible.
																</li>
															</ul>
														</li>
													</ol>
												</div>
											</div>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="indexing">
										<AccordionTrigger className="text-lg font-medium">Indexing</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<ol className="list-decimal pl-5 space-y-3">
												<li>
													Navigate to the Connector Dashboard and select the <strong>Notion</strong>{" "}
													Connector.
												</li>
												<li>
													Place the <strong>Integration Token</strong> under{" "}
													<strong>Step 1 Provide Credentials</strong>.
												</li>
												<li>
													Click <strong>Connect</strong> to establish the connection.
												</li>
											</ol>

											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>Indexing Behavior</AlertTitle>
												<AlertDescription>
													The Notion connector currently indexes everything it has access to. If you
													want to limit specific content being indexed, simply unshare the database
													from Notion with the integration.
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
