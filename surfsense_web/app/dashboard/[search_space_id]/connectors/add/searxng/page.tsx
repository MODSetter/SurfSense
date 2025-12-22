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
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

const searxngFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	host: z
		.string({ required_error: "Host is required." })
		.url({ message: "Enter a valid SearxNG host URL (e.g. https://searxng.example.org)." }),
	api_key: z.string().optional(),
	engines: z.string().optional(),
	categories: z.string().optional(),
	language: z.string().optional(),
	safesearch: z
		.string()
		.regex(/^[0-2]?$/, { message: "SafeSearch must be 0, 1, or 2." })
		.optional(),
	verify_ssl: z.boolean().default(true),
});

type SearxngFormValues = z.infer<typeof searxngFormSchema>;

const parseCommaSeparated = (value?: string | null) => {
	if (!value) return undefined;
	const items = value
		.split(",")
		.map((item) => item.trim())
		.filter((item) => item.length > 0);
	return items.length > 0 ? items : undefined;
};

export default function SearxngConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	const form = useForm<SearxngFormValues>({
		resolver: zodResolver(searxngFormSchema),
		defaultValues: {
			name: "SearxNG Connector",
			host: "",
			api_key: "",
			engines: "",
			categories: "",
			language: "",
			safesearch: "",
			verify_ssl: true,
		},
	});

	const onSubmit = async (values: SearxngFormValues) => {
		setIsSubmitting(true);
		try {
			const config: Record<string, unknown> = {
				SEARXNG_HOST: values.host.trim(),
			};

			const apiKey = values.api_key?.trim();
			if (apiKey) config.SEARXNG_API_KEY = apiKey;

			const engines = parseCommaSeparated(values.engines);
			if (engines) config.SEARXNG_ENGINES = engines;

			const categories = parseCommaSeparated(values.categories);
			if (categories) config.SEARXNG_CATEGORIES = categories;

			const language = values.language?.trim();
			if (language) config.SEARXNG_LANGUAGE = language;

			const safesearch = values.safesearch?.trim();
			if (safesearch) {
				const parsed = Number(safesearch);
				if (!Number.isNaN(parsed)) {
					config.SEARXNG_SAFESEARCH = parsed;
				}
			}

			// Include verify flag only when disabled to keep config minimal
			if (values.verify_ssl === false) {
				config.SEARXNG_VERIFY_SSL = false;
			}

			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.SEARXNG_API,
					config,
					is_indexable: false,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("SearxNG connector created successfully!");
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		} catch (error) {
			console.error("Error creating SearxNG connector:", error);
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

			<div className="mb-8">
				<div className="flex items-center gap-4">
					<div className="flex h-12 w-12 items-center justify-center rounded-lg">
						{getConnectorIcon(EnumConnectorName.SEARXNG_API, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect SearxNG</h1>
						<p className="text-muted-foreground">
							Bring your self-hosted SearxNG meta-search engine into SurfSense.
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
						<CardTitle className="text-2xl font-bold">Connect SearxNG</CardTitle>
						<CardDescription>
							Integrate SurfSense with any SearxNG instance to broaden your search coverage while
							preserving privacy and control.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<Alert className="mb-6 bg-muted">
							<Info className="h-4 w-4" />
							<AlertTitle>SearxNG Instance Required</AlertTitle>
							<AlertDescription>
								You need access to a running SearxNG instance. Refer to the{" "}
								<a
									href="https://docs.searxng.org/admin/installation-docker.html"
									target="_blank"
									rel="noreferrer"
									className="font-medium underline underline-offset-4"
								>
									SearxNG installation guide
								</a>{" "}
								for setup instructions. If your instance requires an API key, include it below.
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
												<Input placeholder="My SearxNG Connector" {...field} />
											</FormControl>
											<FormDescription>A friendly name to identify this connector.</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>

								<FormField
									control={form.control}
									name="host"
									render={({ field }) => (
										<FormItem>
											<FormLabel>SearxNG Host</FormLabel>
											<FormControl>
												<Input placeholder="https://searxng.example.org" {...field} />
											</FormControl>
											<FormDescription>
												Provide the full base URL to your SearxNG instance. Include the protocol
												(http/https).
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
											<FormLabel>API Key (optional)</FormLabel>
											<FormControl>
												<Input
													type="password"
													placeholder="Enter API key if your instance requires one"
													{...field}
												/>
											</FormControl>
											<FormDescription>
												Leave empty if your SearxNG instance does not enforce API keys.
											</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>

								<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
									<FormField
										control={form.control}
										name="engines"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Engines (optional)</FormLabel>
												<FormControl>
													<Input placeholder="google,bing,duckduckgo" {...field} />
												</FormControl>
												<FormDescription>
													Comma-separated list to target specific engines.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									<FormField
										control={form.control}
										name="categories"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Categories (optional)</FormLabel>
												<FormControl>
													<Input placeholder="general,it,science" {...field} />
												</FormControl>
												<FormDescription>
													Comma-separated list of SearxNG categories.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>
								</div>

								<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
									<FormField
										control={form.control}
										name="language"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Preferred Language (optional)</FormLabel>
												<FormControl>
													<Input placeholder="en-US" {...field} />
												</FormControl>
												<FormDescription>
													IETF language tag (e.g. en, en-US). Leave blank to inherit defaults.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									<FormField
										control={form.control}
										name="safesearch"
										render={({ field }) => (
											<FormItem>
												<FormLabel>SafeSearch Level (optional)</FormLabel>
												<FormControl>
													<Input placeholder="0 (off), 1 (moderate), 2 (strict)" {...field} />
												</FormControl>
												<FormDescription>
													Set 0, 1, or 2 to adjust SafeSearch filtering. Leave blank to use the
													instance default.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>
								</div>

								<FormField
									control={form.control}
									name="verify_ssl"
									render={({ field }) => (
										<FormItem className="flex items-center justify-between rounded-lg border p-4">
											<div>
												<FormLabel>Verify SSL Certificates</FormLabel>
												<FormDescription>
													Disable only when connecting to instances with self-signed certificates.
												</FormDescription>
											</div>
											<FormControl>
												<Switch checked={field.value} onCheckedChange={field.onChange} />
											</FormControl>
										</FormItem>
									)}
								/>

								<CardFooter className="flex justify-end px-0">
									<Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
										{isSubmitting ? (
											<>
												<Loader2 className="mr-2 h-4 w-4 animate-spin" />
												Connecting...
											</>
										) : (
											<>
												<Check className="mr-2 h-4 w-4" />
												Connect SearxNG
											</>
										)}
									</Button>
								</CardFooter>
							</form>
						</Form>
					</CardContent>
				</Card>
			</motion.div>
		</div>
	);
}
