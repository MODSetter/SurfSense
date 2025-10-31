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
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const tavilyApiFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_key: z.string().min(10, {
		message: "API key is required and must be valid.",
	}),
});

// Define the type for the form values
type TavilyApiFormValues = z.infer<typeof tavilyApiFormSchema>;

export default function TavilyApiPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<TavilyApiFormValues>({
		resolver: zodResolver(tavilyApiFormSchema),
		defaultValues: {
			name: "Tavily API Connector",
			api_key: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: TavilyApiFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.TAVILY_API,
					config: {
						TAVILY_API_KEY: values.api_key,
					},
					is_indexable: false,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Tavily API connector created successfully!");

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
						{getConnectorIcon(EnumConnectorName.TAVILY_API, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Tavily API</h1>
						<p className="text-muted-foreground">
							Connect Tavily API for AI-powered search capabilities.
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
						<CardTitle className="text-2xl font-bold">Connect Tavily API</CardTitle>
						<CardDescription>
							Integrate with Tavily API to enhance your search capabilities with AI-powered search
							results.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<Alert className="mb-6 bg-muted">
							<Info className="h-4 w-4" />
							<AlertTitle>API Key Required</AlertTitle>
							<AlertDescription>
								You'll need a Tavily API key to use this connector. You can get one by signing up at{" "}
								<a
									href="https://tavily.com"
									target="_blank"
									rel="noopener noreferrer"
									className="font-medium underline underline-offset-4"
								>
									tavily.com
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
												<Input placeholder="My Tavily API Connector" {...field} />
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
											<FormLabel>Tavily API Key</FormLabel>
											<FormControl>
												<Input type="password" placeholder="Enter your Tavily API key" {...field} />
											</FormControl>
											<FormDescription>
												Your API key will be encrypted and stored securely.
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
												Connect Tavily API
											</>
										)}
									</Button>
								</div>
							</form>
						</Form>
					</CardContent>
					<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
						<h4 className="text-sm font-medium">What you get with Tavily API:</h4>
						<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
							<li>AI-powered search results tailored to your queries</li>
							<li>Real-time information from the web</li>
							<li>Enhanced search capabilities for your projects</li>
						</ul>
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
}
