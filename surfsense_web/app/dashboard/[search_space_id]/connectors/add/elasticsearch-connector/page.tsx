"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as RadioGroup from "@radix-ui/react-radio-group";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useId, useState } from "react";
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
import { Badge } from "@/components/ui/badge";
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
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const elasticsearchConnectorFormSchema = z
	.object({
		name: z.string().min(3, {
			message: "Connector name must be at least 3 characters.",
		}),
		endpoint_url: z.string().url({ message: "Please enter a valid Elasticsearch endpoint URL." }),
		auth_method: z.enum(["basic", "api_key"]).default("api_key"),
		username: z.string().optional(),
		password: z.string().optional(),
		ELASTICSEARCH_API_KEY: z.string().optional(),
		indices: z.string().optional(),
		query: z.string().default("*"),
		search_fields: z.string().optional(),
		max_documents: z.number().min(1).max(10000).optional(),
	})
	.refine(
		(data) => {
			if (data.auth_method === "basic") {
				return Boolean(data.username?.trim() && data.password?.trim());
			}
			if (data.auth_method === "api_key") {
				return Boolean(data.ELASTICSEARCH_API_KEY?.trim());
			}
			return true;
		},
		{
			message: "Authentication credentials are required for the selected method.",
			path: ["auth_method"],
		}
	);

// Define the type for the form values
type ElasticsearchConnectorFormValues = z.infer<typeof elasticsearchConnectorFormSchema>;

export default function ElasticsearchConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchParams = useSearchParams();
	// match pattern used in other connector pages: prefer route param, fallback to query param
	const searchSpaceId = (params.search_space_id ?? searchParams?.get("search_space_id")) as string;
	const [isSubmitting, setIsSubmitting] = useState(false);

	const authBasicId = useId();
	const authApiKeyId = useId();

	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<ElasticsearchConnectorFormValues>({
		resolver: zodResolver(elasticsearchConnectorFormSchema),
		defaultValues: {
			name: "Elasticsearch Connector",
			endpoint_url: "",
			auth_method: "api_key",
			username: "",
			password: "",
			ELASTICSEARCH_API_KEY: "",
			indices: "",
			query: "*",
			search_fields: "",
			max_documents: undefined,
		},
	});

	const stringToArray = (str: string): string[] => {
		const items = str
			.split(",")
			.map((item) => item.trim())
			.filter((item) => item.length > 0);
		return Array.from(new Set(items));
	};

	// Handle form submission
	const onSubmit = async (values: ElasticsearchConnectorFormValues) => {
		setIsSubmitting(true);
		if (!searchSpaceId) {
			toast.error(
				"Missing search_space_id (route or ?search_space_id=). Provide it in the URL or pick a search space."
			);
			setIsSubmitting(false);
			return;
		}
		const searchSpaceIdNum = Number(searchSpaceId);
		if (!Number.isInteger(searchSpaceIdNum) || searchSpaceIdNum <= 0) {
			toast.error("Invalid search_space_id. It must be a positive integer.");
			setIsSubmitting(false);
			return;
		}
		try {
			// Send full URL to backend (backend expects ELASTICSEARCH_URL)
			const config: Record<string, string | number | boolean | string[]> = {
				ELASTICSEARCH_URL: values.endpoint_url,
				// default to verifying certs; expose fields for CA/verify if UI added later
				ELASTICSEARCH_VERIFY_CERTS: true,
			};

			if (values.auth_method === "basic") {
				if (values.username) config.ELASTICSEARCH_USERNAME = values.username;
				if (values.password) config.ELASTICSEARCH_PASSWORD = values.password;
			} else if (values.auth_method === "api_key") {
				if (values.ELASTICSEARCH_API_KEY)
					config.ELASTICSEARCH_API_KEY = values.ELASTICSEARCH_API_KEY;
			}

			const indicesInput = values.indices?.trim() ?? "";
			const indicesArr = stringToArray(indicesInput);
			config.ELASTICSEARCH_INDEX =
				indicesArr.length === 0 ? "*" : indicesArr.length === 1 ? indicesArr[0] : indicesArr;

			if (values.query && values.query !== "*") {
				config.ELASTICSEARCH_QUERY = values.query;
			}

			if (values.search_fields?.trim()) {
				// config.ELASTICSEARCH_FIELDS = stringToArray(values.search_fields);
				const fields = stringToArray(values.search_fields);
				config.ELASTICSEARCH_FIELDS = fields;
				config.ELASTICSEARCH_CONTENT_FIELDS = fields;
				if (fields.includes("title")) {
					config.ELASTICSEARCH_TITLE_FIELD = "title";
				}
			}

			if (values.max_documents !== undefined && values.max_documents > 0) {
				config.ELASTICSEARCH_MAX_DOCUMENTS = values.max_documents;
			}

			const connectorPayload = {
				name: values.name,
				connector_type: EnumConnectorName.ELASTICSEARCH_CONNECTOR,
				is_indexable: true,
				last_indexed_at: null,
				periodic_indexing_enabled: false,
				indexing_frequency_minutes: null,
				next_scheduled_at: null,
				config,
			};

			// Use existing hook method
			await createConnector(connectorPayload, searchSpaceIdNum);

			toast.success("Elasticsearch connector created successfully!");
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
						{getConnectorIcon(EnumConnectorName.ELASTICSEARCH_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Elasticsearch</h1>
						<p className="text-muted-foreground">
							Connect to your Elasticsearch cluster to search and index documents.
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
								<CardTitle className="text-2xl font-bold">Connect Elasticsearch Cluster</CardTitle>
								<CardDescription>
									Connect to your Elasticsearch instance to search and index documents for enhanced
									search capabilities.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Form {...form}>
									<form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
										{/* Connector Name */}
										<FormField
											control={form.control}
											name="name"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Connector Name</FormLabel>
													<FormControl>
														<Input placeholder="My Elasticsearch Connector" {...field} />
													</FormControl>
													<FormDescription>
														A friendly name to identify this connector.
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										{/* Connection Details */}
										<div className="space-y-4">
											<h3 className="text-lg font-medium">Connection Details</h3>

											<FormField
												control={form.control}
												name="endpoint_url"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Elasticsearch Endpoint URL</FormLabel>
														<FormControl>
															<Input
																type="url"
																autoComplete="off"
																placeholder="https://your-cluster.es.region.aws.com:443"
																{...field}
															/>
														</FormControl>
														<FormDescription>
															Enter the complete Elasticsearch endpoint URL. We'll automatically
															extract the hostname, port, and SSL settings.
														</FormDescription>
														<FormMessage />
													</FormItem>
												)}
											/>

											{/* Show parsed URL details */}
											{form.watch("endpoint_url") && (
												<div className="rounded-lg border bg-muted/50 p-3">
													<h4 className="text-sm font-medium mb-2">Parsed Connection Details:</h4>
													<div className="text-sm text-muted-foreground space-y-1">
														{(() => {
															try {
																const url = new URL(form.watch("endpoint_url"));
																return (
																	<>
																		<div>
																			<strong>Hostname:</strong> {url.hostname}
																		</div>
																		<div>
																			<strong>Port:</strong>{" "}
																			{url.port || (url.protocol === "https:" ? "443" : "80")}
																		</div>
																		<div>
																			<strong>SSL/TLS:</strong>{" "}
																			{url.protocol === "https:" ? "Enabled" : "Disabled"}
																		</div>
																	</>
																);
															} catch {
																return <div className="text-destructive">Invalid URL format</div>;
															}
														})()}
													</div>
												</div>
											)}
										</div>

										{/* Authentication */}
										<div className="space-y-4">
											<h3 className="text-lg font-medium">Authentication</h3>

											<FormField
												control={form.control}
												name="auth_method"
												render={({ field }) => (
													<FormItem className="space-y-3">
														<FormControl>
															<RadioGroup.Root
																onValueChange={(value) => {
																	field.onChange(value);
																	// Clear auth fields when method changes
																	if (value !== "basic") {
																		form.setValue("username", "");
																		form.setValue("password", "");
																	}
																	if (value !== "api_key") {
																		form.setValue("ELASTICSEARCH_API_KEY", "");
																	}
																}}
																value={field.value}
																className="flex flex-col space-y-2"
															>
																<div className="flex items-center space-x-2">
																	<RadioGroup.Item
																		value="api_key"
																		id={authApiKeyId}
																		className="aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
																	>
																		<RadioGroup.Indicator className="flex items-center justify-center">
																			<div className="h-2.5 w-2.5 rounded-full bg-current" />
																		</RadioGroup.Indicator>
																	</RadioGroup.Item>
																	<Label htmlFor={authApiKeyId}>API Key</Label>
																</div>

																<div className="flex items-center space-x-2">
																	<RadioGroup.Item
																		value="basic"
																		id={authBasicId}
																		className="aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
																	>
																		<RadioGroup.Indicator className="flex items-center justify-center">
																			<div className="h-2.5 w-2.5 rounded-full bg-current" />
																		</RadioGroup.Indicator>
																	</RadioGroup.Item>
																	<Label htmlFor={authBasicId}>Username & Password</Label>
																</div>
															</RadioGroup.Root>
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											{/* Basic Auth Fields */}
											{form.watch("auth_method") === "basic" && (
												<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
													<FormField
														control={form.control}
														name="username"
														render={({ field }) => (
															<FormItem>
																<FormLabel>Username</FormLabel>
																<FormControl>
																	<Input placeholder="elastic" autoComplete="username" {...field} />
																</FormControl>
																<FormMessage />
															</FormItem>
														)}
													/>

													<FormField
														control={form.control}
														name="password"
														render={({ field }) => (
															<FormItem>
																<FormLabel>Password</FormLabel>
																<FormControl>
																	<Input
																		type="password"
																		placeholder="Password"
																		autoComplete="current-password"
																		{...field}
																	/>
																</FormControl>
																<FormMessage />
															</FormItem>
														)}
													/>
												</div>
											)}

											{/* API Key Field */}
											{form.watch("auth_method") === "api_key" && (
												<FormField
													control={form.control}
													name="ELASTICSEARCH_API_KEY"
													render={({ field }) => (
														<FormItem>
															<FormLabel>API Key</FormLabel>
															<FormControl>
																<Input
																	type="password"
																	placeholder="Your API Key Here"
																	autoComplete="off"
																	{...field}
																/>
															</FormControl>
															<FormDescription>
																Enter your Elasticsearch API key (base64 encoded). This will be
																stored securely.
															</FormDescription>
															<FormMessage />
														</FormItem>
													)}
												/>
											)}

											{/* Index Selection */}
											<FormField
												control={form.control}
												name="indices"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Index Selection </FormLabel>
														<FormControl>
															<Input placeholder="logs-*, documents-*, app-logs" {...field} />
														</FormControl>
														<FormDescription>
															Comma-separated indices to search (e.g., "logs-*, documents-*").
														</FormDescription>
														<FormMessage />
													</FormItem>
												)}
											/>

											{/* Show parsed indices as badges */}
											{form.watch("indices")?.trim() && (
												<div className="rounded-lg border bg-muted/50 p-3">
													<h4 className="text-sm font-medium mb-2">Selected Indices:</h4>
													<div className="flex flex-wrap gap-2">
														{stringToArray(form.watch("indices") ?? "").map((index) => (
															<Badge key={index} variant="secondary" className="text-xs">
																{index}
															</Badge>
														))}
													</div>
												</div>
											)}

											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>Index Selection Tips</AlertTitle>
												<AlertDescription className="mt-2">
													<ul className="list-disc pl-4 space-y-1 text-sm">
														<li>Use wildcards like "logs-*" to match multiple indices</li>
														<li>Separate multiple indices with commas</li>
														<li>
															Leave empty to search all accessible indices including internal ones
														</li>
														<li>Choosing specific indices improves search performance</li>
													</ul>
												</AlertDescription>
											</Alert>
										</div>

										{/* Advanced Configuration */}
										<Accordion type="single" collapsible className="w-full">
											<AccordionItem value="advanced">
												<AccordionTrigger>Advanced Configuration</AccordionTrigger>
												<AccordionContent className="space-y-4">
													{/* Default Search Query */}
													<FormField
														control={form.control}
														name="query"
														render={({ field }) => (
															<FormItem>
																<FormLabel>
																	Default Search Query{" "}
																	<span className="text-muted-foreground">(Optional)</span>
																</FormLabel>
																<FormControl>
																	<Input placeholder="*" {...field} />
																</FormControl>
																<FormDescription>
																	Default Elasticsearch query to use for searches. Use "*" to match
																	all documents.
																</FormDescription>
																<FormMessage />
															</FormItem>
														)}
													/>

													{/* Form Fields */}
													<FormField
														control={form.control}
														name="search_fields"
														render={({ field }) => (
															<FormItem>
																<FormLabel>
																	Search Fields{" "}
																	<span className="text-muted-foreground">(Optional)</span>
																</FormLabel>
																<FormControl>
																	<Input placeholder="title, content, description" {...field} />
																</FormControl>
																<FormDescription>
																	Comma-separated list of specific fields to search in (e.g.,
																	"title, content, description"). Leave empty to search all fields.
																</FormDescription>
																<FormMessage />
															</FormItem>
														)}
													/>

													{/* Show parsed search fields as badges */}
													{form.watch("search_fields")?.trim() && (
														<div className="rounded-lg border bg-muted/50 p-3">
															<h4 className="text-sm font-medium mb-2">Search Fields:</h4>
															<div className="flex flex-wrap gap-2">
																{stringToArray(form.watch("search_fields") ?? "").map((field) => (
																	<Badge key={field} variant="outline" className="text-xs">
																		{field}
																	</Badge>
																))}
															</div>
														</div>
													)}

													<FormField
														control={form.control}
														name="max_documents"
														render={({ field }) => (
															<FormItem>
																<FormLabel>
																	Maximum Documents{" "}
																	<span className="text-muted-foreground">(Optional)</span>
																</FormLabel>
																<FormControl>
																	<Input
																		type="number"
																		placeholder="1000"
																		min="1"
																		max="10000"
																		{...field}
																		onChange={(e) =>
																			field.onChange(
																				e.target.value === ""
																					? undefined
																					: parseInt(e.target.value, 10)
																			)
																		}
																	/>
																</FormControl>
																<FormDescription>
																	Maximum number of documents to retrieve per search (1-10,000).
																	Leave empty to use Elasticsearch's default limit.
																</FormDescription>
																<FormMessage />
															</FormItem>
														)}
													/>
												</AccordionContent>
											</AccordionItem>
										</Accordion>

										<Separator />

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
														Connect Elasticsearch
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">
									What you get with Elasticsearch integration:
								</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search across your indexed documents and logs</li>
									<li>Access structured and unstructured data from your cluster</li>
									<li>Leverage existing Elasticsearch indices for enhanced search</li>
									<li>Real-time search capabilities with powerful query features</li>
									<li>Integration with your existing Elasticsearch infrastructure</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">
									Elasticsearch Connector Documentation
								</CardTitle>
								<CardDescription>
									Learn how to set up and use the Elasticsearch connector to search your data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Elasticsearch connector allows you to search and retrieve documents from
										your Elasticsearch cluster. Configure connection details, select specific
										indices, and set search parameters to make your existing data searchable within
										SurfSense.
									</p>
								</div>

								<Accordion type="single" collapsible className="w-full">
									<AccordionItem value="connection">
										<AccordionTrigger className="text-lg font-medium">
											Connection Setup
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<ol className="list-decimal pl-5 space-y-3">
												<li>
													<strong>Endpoint URL:</strong> Enter the complete Elasticsearch endpoint
													URL (e.g., https://your-cluster.es.region.aws.com:443). We'll
													automatically extract hostname, port, and SSL settings.
												</li>
												<li>
													<strong>Authentication:</strong> Choose the appropriate method:
													<ul className="list-disc pl-5 mt-1">
														<li>
															<strong>API Key:</strong> Base64 encoded API key (recommended for
															security)
														</li>
														<li>
															<strong>Username/Password:</strong> Basic authentication credentials
														</li>
													</ul>
												</li>
												<li>
													<strong>Index Selection:</strong> Specify which indices to search using
													comma-separated patterns (e.g., "logs-*, documents-*")
												</li>
											</ol>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="advanced">
										<AccordionTrigger className="text-lg font-medium">
											Advanced Configuration
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<p className="text-muted-foreground">
												Fine-tune your Elasticsearch connector with these optional settings:
											</p>
											<ul className="list-disc pl-5 space-y-2">
												<li>
													<strong>Search Fields:</strong> Limit searches to specific fields (e.g.,
													"title, content") for better relevance
												</li>
												<li>
													<strong>Default Query:</strong> Set a default Elasticsearch query pattern
												</li>
												<li>
													<strong>Max Documents:</strong> Limit the number of documents returned per
													search (1-10,000)
												</li>
											</ul>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="troubleshooting">
										<AccordionTrigger className="text-lg font-medium">
											Troubleshooting
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<div className="space-y-4">
												<div>
													<h4 className="font-medium mb-2">Common Connection Issues:</h4>
													<ul className="list-disc pl-5 space-y-2 text-muted-foreground">
														<li>
															<strong>Connection Refused:</strong> Check hostname and port. Ensure
															Elasticsearch is running.
														</li>
														<li>
															<strong>Authentication Failed:</strong> Verify credentials. For API
															keys, ensure they have proper permissions.
														</li>
														<li>
															<strong>SSL Errors:</strong> Try disabling SSL for local development
															or check certificate validity.
														</li>
														<li>
															<strong>No Indices Found:</strong> Ensure your credentials have
															permission to list and read indices.
														</li>
													</ul>
												</div>

												<Alert className="bg-muted">
													<Info className="h-4 w-4" />
													<AlertTitle>Security Note</AlertTitle>
													<AlertDescription>
														For production environments, use API keys with minimal required
														permissions: cluster monitoring and read access to specific indices.
													</AlertDescription>
												</Alert>
											</div>
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
