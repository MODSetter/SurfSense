"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Globe, Loader2 } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	type SearchSourceConnector,
	useSearchSourceConnectors,
} from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const webcrawlerConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_key: z.string().optional(),
	initial_urls: z.string().optional(),
});

// Define the type for the form values
type WebcrawlerConnectorFormValues = z.infer<typeof webcrawlerConnectorFormSchema>;

export default function WebcrawlerConnectorPage() {
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
	const form = useForm<WebcrawlerConnectorFormValues>({
		resolver: zodResolver(webcrawlerConnectorFormSchema),
		defaultValues: {
			name: "Web Pages",
			api_key: "",
			initial_urls: "",
		},
	});

	useEffect(() => {
		fetchConnectors(parseInt(searchSpaceId))
			.then((data) => {
				if (data && Array.isArray(data)) {
					const connector = data.find(
						(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.WEBCRAWLER_CONNECTOR
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
	const onSubmit = async (values: WebcrawlerConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			const config: Record<string, string> = {};
			
			// Only add API key to config if provided
			if (values.api_key && values.api_key.trim()) {
				config.FIRECRAWL_API_KEY = values.api_key;
			}

			// Parse initial URLs if provided
			if (values.initial_urls && values.initial_urls.trim()) {
				config.INITIAL_URLS = values.initial_urls;
			}

			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.WEBCRAWLER_CONNECTOR,
					config: config,
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Webcrawler connector created successfully!");

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
							{getConnectorIcon(EnumConnectorName.WEBCRAWLER_CONNECTOR, "h-6 w-6")}
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Web Pages</h1>
							<p className="text-muted-foreground">Crawl and index web pages for search.</p>
						</div>
					</div>
				</div>

				{/* Connection Card */}
				{!doesConnectorExist ? (
					<Card>
						<CardHeader>
							<CardTitle>Set Up Web Page crawler</CardTitle>
							<CardDescription>
								Configure your web page crawler to index web pages. Optionally add a Firecrawl API key
								for enhanced crawling capabilities.
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
													<Input placeholder="My Web Crawler" {...field} />
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
												<FormLabel>Firecrawl API Key (Optional)</FormLabel>
												<FormControl>
													<Input 
														type="password" 
														placeholder="fc-xxxxxxxxxxxxx" 
														{...field} 
													/>
												</FormControl>
												<FormDescription>
													Add a Firecrawl API key for enhanced crawling. If not provided, will use
													AsyncChromiumLoader as fallback.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									<FormField
										control={form.control}
										name="initial_urls"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Initial URLs (Optional)</FormLabel>
												<FormControl>
													<Textarea 
														placeholder="https://example.com&#10;https://docs.example.com&#10;https://blog.example.com"
														className="min-h-[100px] font-mono text-sm"
														{...field} 
													/>
												</FormControl>
												<FormDescription>
													Enter URLs to crawl (one per line). You can add more URLs later.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									<div className="space-y-2 pt-2">
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>Crawl any public web page</span>
										</div>
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>Extract markdown content automatically</span>
										</div>
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>Detect content changes and update documents</span>
										</div>
										<div className="flex items-center space-x-2 text-sm text-muted-foreground">
											<Check className="h-4 w-4 text-green-500" />
											<span>Works with or without Firecrawl API key</span>
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
												Setting up...
											</>
										) : (
											<>
												<Globe className="mr-2 h-4 w-4" />
												Create Crawler
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
							<CardTitle>✅ Your web page crawler is successfully set up!</CardTitle>
							<CardDescription>
								You can now add URLs to crawl from the connector management page.
							</CardDescription>
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
								<h4 className="font-medium mb-2">1. Choose Your Crawler Method</h4>
								<p className="text-sm text-muted-foreground">
									<strong>With Firecrawl (Recommended):</strong> Get your API key from{" "}
									<a 
										href="https://firecrawl.dev" 
										target="_blank" 
										rel="noopener noreferrer"
										className="text-primary hover:underline"
									>
										firecrawl.dev
									</a>{" "}
									for faster, more reliable crawling with better content extraction.
								</p>
								<p className="text-sm text-muted-foreground mt-2">
									<strong>Without Firecrawl:</strong> The crawler will use AsyncChromiumLoader as a
									free fallback option. This works well for most websites but may be slower.
								</p>
							</div>
							<div>
								<h4 className="font-medium mb-2">2. Add URLs to Crawl (Optional)</h4>
								<p className="text-sm text-muted-foreground">
									You can add initial URLs now or add them later from the connector management page.
									Enter one URL per line.
								</p>
							</div>
							<div>
								<h4 className="font-medium mb-2">3. Manage Your Crawler</h4>
								<p className="text-sm text-muted-foreground">
									After setup, you can add more URLs, trigger manual crawls, or set up periodic
									indexing to keep your content up-to-date.
								</p>
							</div>
						</CardContent>
					</Card>
				)}
			</motion.div>
		</div>
	);
}