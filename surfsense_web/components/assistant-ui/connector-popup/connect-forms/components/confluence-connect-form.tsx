"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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

const confluenceConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	base_url: z.string().url({ message: "Please enter a valid Confluence base URL." }),
	email: z.string().email({ message: "Please enter a valid email address." }),
	api_token: z.string().min(10, {
		message: "Confluence API Token is required and must be valid.",
	}),
});

type ConfluenceConnectorFormValues = z.infer<typeof confluenceConnectorFormSchema>;

export const ConfluenceConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const form = useForm<ConfluenceConnectorFormValues>({
		resolver: zodResolver(confluenceConnectorFormSchema),
		defaultValues: {
			name: "Confluence Connector",
			base_url: "",
			email: "",
			api_token: "",
		},
	});

	const handleSubmit = async (values: ConfluenceConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.CONFLUENCE_CONNECTOR,
				config: {
					CONFLUENCE_BASE_URL: values.base_url,
					CONFLUENCE_EMAIL: values.email,
					CONFLUENCE_API_TOKEN: values.api_token,
				},
				is_indexable: true,
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
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-center [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
				<Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0 ml-1" />
				<div className="-ml-1">
					<AlertTitle className="text-xs sm:text-sm">API Token Required</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						You'll need a Confluence API Token to use this connector. You can create one from{" "}
						<a
							href="https://id.atlassian.com/manage-profile/security/api-tokens"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							Atlassian Account Settings
						</a>
					</AlertDescription>
				</div>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="confluence-connect-form"
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
											placeholder="My Confluence Connector"
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

						<FormField
							control={form.control}
							name="base_url"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Confluence Base URL</FormLabel>
									<FormControl>
										<Input
											type="url"
											placeholder="https://your-domain.atlassian.net"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										The base URL of your Confluence instance (e.g.,
										https://your-domain.atlassian.net).
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
									<FormLabel className="text-xs sm:text-sm">Email Address</FormLabel>
									<FormControl>
										<Input
											type="email"
											placeholder="your-email@example.com"
											autoComplete="email"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										The email address associated with your Atlassian account.
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
									<FormLabel className="text-xs sm:text-sm">API Token</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder="Your API Token"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Your Confluence API Token will be encrypted and stored securely.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

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
			{getConnectorBenefits(EnumConnectorName.CONFLUENCE_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">
						What you get with Confluence integration:
					</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.CONFLUENCE_CONNECTOR)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}

			{/* Documentation Section */}
			<Accordion
				type="single"
				collapsible
				className="w-full border border-border rounded-xl bg-slate-400/5 dark:bg-white/5"
			>
				<AccordionItem value="documentation" className="border-0">
					<AccordionTrigger className="text-sm sm:text-base font-medium px-3 sm:px-6 no-underline hover:no-underline">
						Documentation
					</AccordionTrigger>
					<AccordionContent className="px-3 sm:px-6 pb-3 sm:pb-6 space-y-6">
						<div>
							<h3 className="text-sm sm:text-base font-semibold mb-2">How it works</h3>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								The Confluence connector uses the Confluence REST API to fetch all pages and
								comments that your account has access to within your Confluence instance.
							</p>
							<ul className="mt-2 list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
								<li>
									For follow up indexing runs, the connector retrieves pages and comments that have
									been updated since the last indexing attempt.
								</li>
								<li>
									Indexing is configured to run periodically, so updates should appear in your
									search results within minutes.
								</li>
							</ul>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">Authorization</h3>
								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 mb-4">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">
										Read-Only Access is Sufficient
									</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										You only need read access for this connector to work. The API Token will only be
										used to read your Confluence data.
									</AlertDescription>
								</Alert>

								<div className="space-y-4 sm:space-y-6">
									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 1: Create an API Token
										</h4>
										<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground">
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
												</a>{" "}
												in your browser.
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
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 2: Grant necessary access
										</h4>
										<p className="text-[10px] sm:text-xs text-muted-foreground mb-3">
											The API Token will have access to all spaces and pages that your user account
											can see. Make sure your account has appropriate permissions for the spaces you
											want to index.
										</p>
										<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
											<Info className="h-3 w-3 sm:h-4 sm:w-4" />
											<AlertTitle className="text-[10px] sm:text-xs">Data Privacy</AlertTitle>
											<AlertDescription className="text-[9px] sm:text-[10px]">
												Only pages, comments, and basic metadata will be indexed. Confluence
												attachments and linked files are not indexed by this connector.
											</AlertDescription>
										</Alert>
									</div>
								</div>
							</div>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">Indexing</h3>
								<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground mb-4">
									<li>
										Navigate to the Connector Dashboard and select the <strong>Confluence</strong>{" "}
										Connector.
									</li>
									<li>
										Enter your <strong>Confluence Instance URL</strong> (e.g.,
										https://yourcompany.atlassian.net)
									</li>
									<li>
										Enter your <strong>Email Address</strong> associated with your Atlassian account
									</li>
									<li>
										Place your <strong>API Token</strong> in the form field.
									</li>
									<li>
										Click <strong>Connect</strong> to establish the connection.
									</li>
									<li>Once connected, your Confluence pages will be indexed automatically.</li>
								</ol>

								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">What Gets Indexed</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										<p className="mb-2">The Confluence connector indexes the following data:</p>
										<ul className="list-disc pl-5 space-y-1">
											<li>All pages from accessible spaces</li>
											<li>Page content and metadata</li>
											<li>Comments on pages (both footer and inline comments)</li>
											<li>Page titles and descriptions</li>
										</ul>
									</AlertDescription>
								</Alert>
							</div>
						</div>
					</AccordionContent>
				</AccordionItem>
			</Accordion>
		</div>
	);
};
