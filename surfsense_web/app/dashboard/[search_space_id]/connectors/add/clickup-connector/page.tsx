"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ExternalLink, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
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
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const clickupConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_token: z.string().min(10, {
		message: "ClickUp API Token is required and must be valid.",
	}),
});

// Define the type for the form values
type ClickUpConnectorFormValues = z.infer<typeof clickupConnectorFormSchema>;

export default function ClickUpConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const { createConnector } = useSearchSourceConnectors();
	const [isLoading, setIsLoading] = useState(false);
	const [showApiToken, setShowApiToken] = useState(false);

	// Initialize the form with react-hook-form and zod validation
	const form = useForm<ClickUpConnectorFormValues>({
		resolver: zodResolver(clickupConnectorFormSchema),
		defaultValues: {
			name: "ClickUp Connector",
			api_token: "",
		},
	});

	// Handle form submission
	async function onSubmit(values: ClickUpConnectorFormValues) {
		setIsLoading(true);

		try {
			const connectorData = {
				name: values.name,
				connector_type: EnumConnectorName.CLICKUP_CONNECTOR,
				is_indexable: true,
				config: {
					CLICKUP_API_TOKEN: values.api_token,
				},
				last_indexed_at: null,
				periodic_indexing_enabled: false,
				indexing_frequency_minutes: null,
				next_scheduled_at: null,
			};

			await createConnector(connectorData, parseInt(searchSpaceId));

			toast.success("ClickUp connector created successfully!");
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		} catch (error) {
			console.error("Error creating ClickUp connector:", error);
			toast.error("Failed to create ClickUp connector. Please try again.");
		} finally {
			setIsLoading(false);
		}
	}

	return (
		<div className="container mx-auto py-6 max-w-2xl">
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
						{getConnectorIcon(EnumConnectorName.CLICKUP_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect ClickUp</h1>
						<p className="text-muted-foreground">
							Connect your ClickUp workspace to search tasks and projects.
						</p>
					</div>
				</div>
			</div>

			<Card>
				<CardHeader>
					<CardTitle>ClickUp Configuration</CardTitle>
					<CardDescription>
						Enter your ClickUp API token to connect your workspace. You can generate a personal API
						token from your ClickUp settings.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<Form {...form}>
						<form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
							<FormField
								control={form.control}
								name="name"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Connector Name</FormLabel>
										<FormControl>
											<Input placeholder="ClickUp Connector" {...field} />
										</FormControl>
										<FormDescription>
											A friendly name to identify this ClickUp connector.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="api_token"
								render={({ field }) => (
									<FormItem>
										<FormLabel>ClickUp API Token</FormLabel>
										<FormControl>
											<div className="relative">
												<Input
													type={showApiToken ? "text" : "password"}
													placeholder="pk_..."
													{...field}
													className="pr-10"
												/>
												<Button
													type="button"
													variant="ghost"
													size="sm"
													className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
													onClick={() => setShowApiToken(!showApiToken)}
												>
													{showApiToken ? (
														<EyeOff className="h-4 w-4" />
													) : (
														<Eye className="h-4 w-4" />
													)}
												</Button>
											</div>
										</FormControl>
										<FormDescription>
											Your ClickUp personal API token. You can generate one in your{" "}
											<Link
												href="https://app.clickup.com/settings/apps"
												target="_blank"
												className="text-primary hover:underline inline-flex items-center"
											>
												ClickUp settings
												<ExternalLink className="ml-1 h-3 w-3" />
											</Link>
											.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							<div className="flex justify-end space-x-4">
								<Button
									type="button"
									variant="outline"
									onClick={() => router.back()}
									disabled={isLoading}
								>
									Cancel
								</Button>
								<Button type="submit" disabled={isLoading}>
									{isLoading ? "Creating..." : "Create Connector"}
								</Button>
							</div>
						</form>
					</Form>
				</CardContent>
			</Card>

			<Card className="mt-6">
				<CardHeader>
					<CardTitle className="text-lg">How to get your ClickUp API Token</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="space-y-2">
						<p className="text-sm text-muted-foreground">1. Log in to your ClickUp account</p>
						<p className="text-sm text-muted-foreground">
							2. Click your avatar in the upper-right corner and select "Settings"
						</p>
						<p className="text-sm text-muted-foreground">3. In the sidebar, click "Apps"</p>
						<p className="text-sm text-muted-foreground">
							4. Under "API Token", click "Generate" or "Regenerate"
						</p>
						<p className="text-sm text-muted-foreground">
							5. Copy the generated token and paste it above
						</p>
					</div>
					<div className="mt-4">
						<Link
							href="https://app.clickup.com/settings/apps"
							target="_blank"
							className="inline-flex items-center text-sm text-primary hover:underline"
						>
							Go to ClickUp API Settings
							<ExternalLink className="ml-1 h-3 w-3" />
						</Link>
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
