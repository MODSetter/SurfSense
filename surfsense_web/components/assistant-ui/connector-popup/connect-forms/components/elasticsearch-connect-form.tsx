"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { DateRangeSelector } from "../../components/date-range-selector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const elasticsearchConnectorFormSchema = z
	.object({
		name: z.string().min(3, {
			message: "Connector name must be at least 3 characters.",
		}),
		endpoint_url: z.string().url({ message: "Please enter a valid Elasticsearch endpoint URL." }),
		auth_method: z.enum(["basic", "api_key"]),
		username: z.string().optional(),
		password: z.string().optional(),
		ELASTICSEARCH_API_KEY: z.string().optional(),
		indices: z.string().optional(),
		query: z.string(),
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

type ElasticsearchConnectorFormValues = z.infer<typeof elasticsearchConnectorFormSchema>;

export const ElasticsearchConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const authBasicId = useId();
	const authApiKeyId = useId();
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");

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

	const handleSubmit = async (values: ElasticsearchConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
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

			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.ELASTICSEARCH_CONNECTOR,
				config,
				is_indexable: true,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: periodicEnabled,
				indexing_frequency_minutes: periodicEnabled ? parseInt(frequencyMinutes, 10) : null,
				next_scheduled_at: null,
				startDate,
				endDate,
				periodicEnabled,
				frequencyMinutes,
			});
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert>
				<Info />
				<AlertTitle>API Key Required</AlertTitle>
				<AlertDescription>
					Enter your Elasticsearch cluster endpoint URL and authentication credentials to connect.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="elasticsearch-connect-form"
						onSubmit={form.handleSubmit(handleSubmit)}
						className="space-y-4 sm:space-y-6"
					>
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Connector Name</FormLabel>
									<FormControl>
										<Input
											placeholder="My Elasticsearch Connector"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										A friendly name to identify this connector.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Connection Details */}
						<div className="space-y-4">
							<h3 className="text-sm sm:text-base font-medium">Connection Details</h3>

							<FormField
								control={form.control}
								name="endpoint_url"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">Elasticsearch Endpoint URL</FormLabel>
										<FormControl>
											<Input
												type="url"
												autoComplete="off"
												placeholder="https://your-cluster.es.region.aws.com:443"
												className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											Enter the complete Elasticsearch endpoint URL. We'll automatically extract the
											hostname, port, and SSL settings.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							{/* Show parsed URL details */}
							{form.watch("endpoint_url") && (
								<div className="rounded-lg border border-border bg-muted/50 p-3">
									<h4 className="text-[10px] sm:text-xs font-medium mb-2">
										Parsed Connection Details:
									</h4>
									<div className="text-[10px] sm:text-xs text-muted-foreground space-y-1">
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
							<h3 className="text-sm sm:text-base font-medium">Authentication</h3>

							<FormField
								control={form.control}
								name="auth_method"
								render={({ field }) => (
									<FormItem className="space-y-3">
										<FormControl>
											<RadioGroup
												onValueChange={(value) => {
													field.onChange(value);
													if (value !== "basic") {
														form.setValue("username", "");
														form.setValue("password", "");
													}
													if (value !== "api_key") {
														form.setValue("ELASTICSEARCH_API_KEY", "");
													}
												}}
												value={field.value}
												className="flex flex-col gap-2"
											>
												<div className="flex items-center gap-2">
													<RadioGroupItem value="api_key" id={authApiKeyId} />
													<Label htmlFor={authApiKeyId} className="text-xs sm:text-sm">
														API Key
													</Label>
												</div>

												<div className="flex items-center gap-2">
													<RadioGroupItem value="basic" id={authBasicId} />
													<Label htmlFor={authBasicId} className="text-xs sm:text-sm">
														Username & Password
													</Label>
												</div>
											</RadioGroup>
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
												<FormLabel className="text-xs sm:text-sm">Username</FormLabel>
												<FormControl>
													<Input
														placeholder="elastic"
														autoComplete="username"
														className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
														disabled={isSubmitting}
														{...field}
													/>
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
												<FormLabel className="text-xs sm:text-sm">Password</FormLabel>
												<FormControl>
													<Input
														type="password"
														placeholder="Password"
														autoComplete="current-password"
														className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
														disabled={isSubmitting}
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
											<FormLabel className="text-xs sm:text-sm">API Key</FormLabel>
											<FormControl>
												<Input
													type="password"
													placeholder="Your API Key Here"
													autoComplete="off"
													className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
													disabled={isSubmitting}
													{...field}
												/>
											</FormControl>
											<FormDescription className="text-[10px] sm:text-xs">
												Enter your Elasticsearch API key (base64 encoded). This will be stored
												securely.
											</FormDescription>
											<FormMessage />
										</FormItem>
									)}
								/>
							)}
						</div>

						{/* Index Selection */}
						<FormField
							control={form.control}
							name="indices"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Index Selection</FormLabel>
									<FormControl>
										<Input
											placeholder="logs-*, documents-*, app-logs"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Comma-separated indices to search (e.g., "logs-*, documents-*").
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Show parsed indices as badges */}
						{form.watch("indices")?.trim() && (
							<div className="rounded-lg border border-border bg-muted/50 p-3">
								<h4 className="text-[10px] sm:text-xs font-medium mb-2">Selected Indices:</h4>
								<div className="flex flex-wrap gap-2">
									{stringToArray(form.watch("indices") ?? "").map((index) => (
										<Badge key={index} variant="secondary" className="text-[10px]">
											{index}
										</Badge>
									))}
								</div>
							</div>
						)}

						<Alert>
							<Info />
							<AlertTitle>Index Selection Tips</AlertTitle>
							<AlertDescription>
								<ul className="list-disc pl-4 space-y-1">
									<li>Use wildcards like "logs-*" to match multiple indices</li>
									<li>Separate multiple indices with commas</li>
									<li>Leave empty to search all accessible indices including internal ones</li>
									<li>Choosing specific indices improves search performance</li>
								</ul>
							</AlertDescription>
						</Alert>

						{/* Advanced Configuration */}
						<Accordion type="single" collapsible className="w-full">
							<AccordionItem value="advanced">
								<AccordionTrigger className="text-xs sm:text-sm">
									Advanced Configuration
								</AccordionTrigger>
								<AccordionContent className="space-y-4">
									{/* Default Search Query */}
									<FormField
										control={form.control}
										name="query"
										render={({ field }) => (
											<FormItem>
												<FormLabel className="text-xs sm:text-sm">
													Default Search Query{" "}
													<span className="text-muted-foreground">(Optional)</span>
												</FormLabel>
												<FormControl>
													<Input
														placeholder="*"
														className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
														disabled={isSubmitting}
														{...field}
													/>
												</FormControl>
												<FormDescription className="text-[10px] sm:text-xs">
													Default Elasticsearch query to use for searches. Use "*" to match all
													documents.
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
												<FormLabel className="text-xs sm:text-sm">
													Search Fields <span className="text-muted-foreground">(Optional)</span>
												</FormLabel>
												<FormControl>
													<Input
														placeholder="title, content, description"
														className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
														disabled={isSubmitting}
														{...field}
													/>
												</FormControl>
												<FormDescription className="text-[10px] sm:text-xs">
													Comma-separated list of specific fields to search in (e.g., "title,
													content, description"). Leave empty to search all fields.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									{/* Show parsed search fields as badges */}
									{form.watch("search_fields")?.trim() && (
										<div className="rounded-lg border border-border bg-muted/50 p-3">
											<h4 className="text-[10px] sm:text-xs font-medium mb-2">Search Fields:</h4>
											<div className="flex flex-wrap gap-2">
												{stringToArray(form.watch("search_fields") ?? "").map((field) => (
													<Badge key={field} variant="outline" className="text-[10px]">
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
												<FormLabel className="text-xs sm:text-sm">
													Maximum Documents{" "}
													<span className="text-muted-foreground">(Optional)</span>
												</FormLabel>
												<FormControl>
													<Input
														type="number"
														placeholder="1000"
														min="1"
														max="10000"
														className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
														disabled={isSubmitting}
														{...field}
														onChange={(e) =>
															field.onChange(
																e.target.value === "" ? undefined : parseInt(e.target.value, 10)
															)
														}
													/>
												</FormControl>
												<FormDescription className="text-[10px] sm:text-xs">
													Maximum number of documents to retrieve per search (1-10,000). Leave empty
													to use Elasticsearch's default limit.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>
								</AccordionContent>
							</AccordionItem>
						</Accordion>

						{/* Indexing Configuration */}
						<div className="space-y-4 pt-4 border-t border-slate-400/20">
							<h3 className="text-sm sm:text-base font-medium">Indexing Configuration</h3>

							{/* Date Range Selector */}
							<DateRangeSelector
								startDate={startDate}
								endDate={endDate}
								onStartDateChange={setStartDate}
								onEndDateChange={setEndDate}
							/>

							{/* Periodic Sync Config */}
							<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
								<div className="flex items-center justify-between">
									<div className="space-y-1">
										<h3 className="font-medium text-sm sm:text-base">Enable Periodic Sync</h3>
										<p className="text-xs sm:text-sm text-muted-foreground">
											Automatically re-index at regular intervals
										</p>
									</div>
									<Switch
										checked={periodicEnabled}
										onCheckedChange={setPeriodicEnabled}
										disabled={isSubmitting}
									/>
								</div>

								{periodicEnabled && (
									<div className="mt-4 pt-4 border-t border-slate-400/20 space-y-3">
										<div className="space-y-2">
											<Label htmlFor="frequency" className="text-xs sm:text-sm">
												Sync Frequency
											</Label>
											<Select
												value={frequencyMinutes}
												onValueChange={setFrequencyMinutes}
												disabled={isSubmitting}
											>
												<SelectTrigger
													id="frequency"
													className="w-full bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
												>
													<SelectValue placeholder="Select frequency" />
												</SelectTrigger>
												<SelectContent className="z-[100]">
													<SelectItem value="5" className="text-xs sm:text-sm">
														Every 5 minutes
													</SelectItem>
													<SelectItem value="15" className="text-xs sm:text-sm">
														Every 15 minutes
													</SelectItem>
													<SelectItem value="60" className="text-xs sm:text-sm">
														Every hour
													</SelectItem>
													<SelectItem value="360" className="text-xs sm:text-sm">
														Every 6 hours
													</SelectItem>
													<SelectItem value="720" className="text-xs sm:text-sm">
														Every 12 hours
													</SelectItem>
													<SelectItem value="1440" className="text-xs sm:text-sm">
														Daily
													</SelectItem>
													<SelectItem value="10080" className="text-xs sm:text-sm">
														Weekly
													</SelectItem>
												</SelectContent>
											</Select>
										</div>
									</div>
								)}
							</div>
						</div>
					</form>
				</Form>
			</div>

			{/* What you get section */}
			{getConnectorBenefits(EnumConnectorName.ELASTICSEARCH_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">
						What you get with Elasticsearch integration:
					</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.ELASTICSEARCH_CONNECTOR)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
};
