"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const baiduSearchApiFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_key: z.string().min(10, {
		message: "API key is required and must be valid.",
	}),
	model: z.string().optional(),
	search_source: z.enum(["baidu_search_v1", "baidu_search_v2"]).optional(),
	enable_deep_search: z.boolean().default(false),
});

// Define the type for the form values
type BaiduSearchApiFormValues = z.infer<typeof baiduSearchApiFormSchema>;

export default function BaiduSearchApiPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<BaiduSearchApiFormValues>({
		resolver: zodResolver(baiduSearchApiFormSchema),
		defaultValues: {
			name: "Baidu Search Connector",
			api_key: "",
			model: "ernie-3.5-8k",
			search_source: "baidu_search_v2",
			enable_deep_search: false,
		},
	});

	// Handle form submission
	const onSubmit = async (values: BaiduSearchApiFormValues) => {
		setIsSubmitting(true);
		try {
			// Build config object
			const config: Record<string, unknown> = {
				BAIDU_API_KEY: values.api_key,
			};

			// Add optional parameters if provided
			if (values.model) {
				config.BAIDU_MODEL = values.model;
			}
			if (values.search_source) {
				config.BAIDU_SEARCH_SOURCE = values.search_source;
			}
			if (values.enable_deep_search !== undefined) {
				config.BAIDU_ENABLE_DEEP_SEARCH = values.enable_deep_search;
			}

			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.BAIDU_SEARCH_API,
					config,
					is_indexable: false,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Baidu Search connector created successfully!");

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
						{getConnectorIcon(EnumConnectorName.BAIDU_SEARCH_API, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Baidu Search</h1>
						<p className="text-muted-foreground">
							Connect Baidu AI Search for intelligent Chinese web search capabilities.
						</p>
					</div>
				</div>
			</div>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Card className="border-2 border-border">
					<CardHeader>
						<CardTitle className="text-2xl font-bold">Connect Baidu Search</CardTitle>
						<CardDescription>
							Integrate with Baidu AI Search to enhance your search capabilities with intelligent
							Chinese web search results.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<Alert className="mb-6 bg-muted">
							<Info className="h-4 w-4" />
							<AlertTitle>API Key Required</AlertTitle>
							<AlertDescription>
								You'll need a Baidu AppBuilder API key to use this connector. You can get one by
								signing up at{" "}
								<a
									href="https://qianfan.cloud.baidu.com/"
									target="_blank"
									rel="noopener noreferrer"
									className="font-medium underline underline-offset-4"
								>
									qianfan.cloud.baidu.com
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
												<Input placeholder="My Baidu Search Connector" {...field} />
											</FormControl>
											<FormDescription>A friendly name to identify this connector.</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>

								<FormField
									control={form.control}
									name="api_key"
									render={({ field }) => (
										<FormItem>
											<FormLabel>Baidu AppBuilder API Key</FormLabel>
											<FormControl>
												<Input type="password" placeholder="Enter your Baidu API key" {...field} />
											</FormControl>
											<FormDescription>
												Your API key will be encrypted and stored securely.
											</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>

								<FormField
									control={form.control}
									name="model"
									render={({ field }) => (
										<FormItem>
											<FormLabel>Model (Optional)</FormLabel>
											<Select onValueChange={field.onChange} defaultValue={field.value}>
												<FormControl>
													<SelectTrigger>
														<SelectValue placeholder="Select a model" />
													</SelectTrigger>
												</FormControl>
												<SelectContent>
													<SelectItem value="ernie-3.5-8k">ERNIE 3.5 8K</SelectItem>
													<SelectItem value="ernie-4.5-turbo-32k">ERNIE 4.5 Turbo 32K</SelectItem>
													<SelectItem value="ernie-4.5-turbo-128k">ERNIE 4.5 Turbo 128K</SelectItem>
													<SelectItem value="deepseek-v3">DeepSeek V3</SelectItem>
													<SelectItem value="qwen3-235b-a22b-instruct-2507">Qwen3 235B</SelectItem>
												</SelectContent>
											</Select>
											<FormDescription>
												The language model used for search summarization. Default: ERNIE 3.5 8K.
											</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>

								<FormField
									control={form.control}
									name="search_source"
									render={({ field }) => (
										<FormItem>
											<FormLabel>Search Source (Optional)</FormLabel>
											<Select onValueChange={field.onChange} defaultValue={field.value}>
												<FormControl>
													<SelectTrigger>
														<SelectValue placeholder="Select search source" />
													</SelectTrigger>
												</FormControl>
												<SelectContent>
													<SelectItem value="baidu_search_v1">Baidu Search V1</SelectItem>
													<SelectItem value="baidu_search_v2">
														Baidu Search V2 (Recommended)
													</SelectItem>
												</SelectContent>
											</Select>
											<FormDescription>
												V2 provides better performance and richer content. Default: V2.
											</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>

								<FormField
									control={form.control}
									name="enable_deep_search"
									render={({ field }) => (
										<FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
											<div className="space-y-0.5">
												<FormLabel className="text-base">Enable Deep Search</FormLabel>
												<FormDescription>
													Deep search retrieves up to 100 results per type (may incur additional
													costs).
												</FormDescription>
											</div>
											<FormControl>
												<Switch checked={field.value} onCheckedChange={field.onChange} />
											</FormControl>
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
												Connect Baidu Search
											</>
										)}
									</Button>
								</div>
							</form>
						</Form>
					</CardContent>
					<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
						<h4 className="text-sm font-medium">What you get with Baidu Search:</h4>
						<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
							<li>Intelligent search tailored for Chinese web content</li>
							<li>Real-time information from Baidu's search index</li>
							<li>AI-powered summarization with source references</li>
							<li>Support for web, video, and image search results</li>
						</ul>
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
}
