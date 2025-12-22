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
const linearConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_key: z
		.string()
		.min(10, {
			message: "Linear API Key is required and must be valid.",
		})
		.regex(/^lin_api_/, {
			message: "Linear API Key should start with 'lin_api_'",
		}),
});

// Define the type for the form values
type LinearConnectorFormValues = z.infer<typeof linearConnectorFormSchema>;

export default function LinearConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<LinearConnectorFormValues>({
		resolver: zodResolver(linearConnectorFormSchema),
		defaultValues: {
			name: "Linear Connector",
			api_key: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: LinearConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.LINEAR_CONNECTOR,
					config: {
						LINEAR_API_KEY: values.api_key,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Linear connector created successfully!");

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
						{getConnectorIcon(EnumConnectorName.LINEAR_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Linear</h1>
						<p className="text-muted-foreground">
							Connect your Linear workspace to search issues and projects.
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
								<CardTitle className="text-2xl font-bold">Connect Linear Workspace</CardTitle>
								<CardDescription>
									Integrate with Linear to search and retrieve information from your issues and
									comments. This connector can index your Linear content for search.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Alert className="mb-6 bg-muted">
									<Info className="h-4 w-4" />
									<AlertTitle>Linear API Key Required</AlertTitle>
									<AlertDescription>
										You'll need a Linear API Key to use this connector. You can create a Linear API
										key from{" "}
										<a
											href="https://linear.app/settings/api"
											target="_blank"
											rel="noopener noreferrer"
											className="font-medium underline underline-offset-4"
										>
											Linear API Settings
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
														<Input placeholder="My Linear Connector" {...field} />
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
													<FormLabel>Linear API Key</FormLabel>
													<FormControl>
														<Input type="password" placeholder="lin_api_..." {...field} />
													</FormControl>
													<FormDescription>
														Your Linear API Key will be encrypted and stored securely. It typically
														starts with "lin_api_".
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
														Connect Linear
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Linear integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through all your Linear issues and comments</li>
									<li>Access issue titles, descriptions, and full discussion threads</li>
									<li>Connect your team's project management directly to your search space</li>
									<li>Keep your search results up-to-date with latest Linear content</li>
									<li>Index your Linear issues for enhanced search capabilities</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Linear Connector Documentation</CardTitle>
								<CardDescription>
									Learn how to set up and use the Linear connector to index your project management
									data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Linear connector uses the Linear GraphQL API to fetch all issues and
										comments that the API key has access to within a workspace.
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
													You only need a read-only API key for this connector to work. This limits
													the permissions to just reading your Linear data.
												</AlertDescription>
											</Alert>

											<div className="space-y-6">
												<div>
													<h4 className="font-medium mb-2">Step 1: Create an API key</h4>
													<ol className="list-decimal pl-5 space-y-3">
														<li>Log in to your Linear account</li>
														<li>
															Navigate to{" "}
															<a
																href="https://linear.app/settings/api"
																target="_blank"
																rel="noopener noreferrer"
																className="font-medium underline underline-offset-4"
															>
																https://linear.app/settings/api
															</a>{" "}
															in your browser.
														</li>
														<li>Alternatively, click on your profile picture → Settings → API</li>
														<li>
															Click the <strong>+ New API key</strong> button.
														</li>
														<li>Enter a description for your key (like "Search Connector").</li>
														<li>Select "Read-only" as the permission.</li>
														<li>
															Click <strong>Create</strong> to generate the API key.
														</li>
														<li>
															Copy the generated API key that starts with 'lin_api_' as it will only
															be shown once.
														</li>
													</ol>
												</div>

												<div>
													<h4 className="font-medium mb-2">Step 2: Grant necessary access</h4>
													<p className="text-muted-foreground mb-3">
														The API key will have access to all issues and comments that your user
														account can see. If you're creating the key as an admin, it will have
														access to all issues in the workspace.
													</p>
													<Alert className="bg-muted">
														<Info className="h-4 w-4" />
														<AlertTitle>Data Privacy</AlertTitle>
														<AlertDescription>
															Only issues and comments will be indexed. Linear attachments and
															linked files are not indexed by this connector.
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
													Navigate to the Connector Dashboard and select the <strong>Linear</strong>{" "}
													Connector.
												</li>
												<li>
													Place the <strong>API Key</strong> in the form field.
												</li>
												<li>
													Click <strong>Connect</strong> to establish the connection.
												</li>
												<li>Once connected, your Linear issues will be indexed automatically.</li>
											</ol>

											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>What Gets Indexed</AlertTitle>
												<AlertDescription>
													<p className="mb-2">The Linear connector indexes the following data:</p>
													<ul className="list-disc pl-5">
														<li>Issue titles and identifiers (e.g., PROJ-123)</li>
														<li>Issue descriptions</li>
														<li>Issue comments</li>
														<li>Issue status and metadata</li>
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
