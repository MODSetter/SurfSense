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

const notionConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	integration_token: z.string().min(10, {
		message: "Notion Integration Token is required and must be valid.",
	}),
});

type NotionConnectorFormValues = z.infer<typeof notionConnectorFormSchema>;

export const NotionConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const form = useForm<NotionConnectorFormValues>({
		resolver: zodResolver(notionConnectorFormSchema),
		defaultValues: {
			name: "Notion Connector",
			integration_token: "",
		},
	});

	const handleSubmit = async (values: NotionConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.NOTION_CONNECTOR,
				config: {
					NOTION_INTEGRATION_TOKEN: values.integration_token,
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
					<AlertTitle className="text-xs sm:text-sm">Integration Token Required</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						You'll need a Notion Integration Token to use this connector. You can create one from{" "}
						<a
							href="https://www.notion.so/my-integrations"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							Notion Integrations
						</a>
					</AlertDescription>
				</div>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="notion-connect-form"
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
											placeholder="My Notion Connector"
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
							name="integration_token"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Notion Integration Token</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder="ntn_..."
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Your Notion Integration Token will be encrypted and stored securely. It
										typically starts with "ntn_".
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
			{getConnectorBenefits(EnumConnectorName.NOTION_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">What you get with Notion integration:</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.NOTION_CONNECTOR)?.map((benefit) => (
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
								The Notion connector uses the Notion API to fetch pages from all accessible
								workspaces that the integration token has access to.
							</p>
							<ul className="mt-2 list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
								<li>
									For follow up indexing runs, the connector retrieves pages that have been updated
									since the last indexing attempt.
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
										Integration Token Required
									</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										You need to create a Notion integration and share pages with it to get access.
										The integration needs read access to pages.
									</AlertDescription>
								</Alert>

								<div className="space-y-4 sm:space-y-6">
									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 1: Create a Notion Integration
										</h4>
										<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground">
											<li>
												Go to{" "}
												<a
													href="https://www.notion.so/my-integrations"
													target="_blank"
													rel="noopener noreferrer"
													className="font-medium underline underline-offset-4"
												>
													https://www.notion.so/my-integrations
												</a>
											</li>
											<li>
												Click <strong>+ New integration</strong>
											</li>
											<li>Enter a name for your integration (e.g., "Search Connector")</li>
											<li>Select your workspace</li>
											<li>
												Under <strong>Capabilities</strong>, enable <strong>Read content</strong>
											</li>
											<li>
												Click <strong>Submit</strong> to create the integration
											</li>
											<li>
												Copy the <strong>Internal Integration Token</strong> (starts with "ntn_")
											</li>
										</ol>
									</div>

									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 2: Share Pages with Integration
										</h4>
										<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground">
											<li>Open the Notion pages or databases you want to index</li>
											<li>
												Click the <strong>⋯</strong> (three dots) menu in the top right
											</li>
											<li>
												Select <strong>Add connections</strong> or <strong>Connections</strong>
											</li>
											<li>Search for and select your integration</li>
											<li>Repeat for all pages you want to index</li>
										</ol>
										<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 mt-3">
											<Info className="h-3 w-3 sm:h-4 sm:w-4" />
											<AlertTitle className="text-[10px] sm:text-xs">Important</AlertTitle>
											<AlertDescription className="text-[9px] sm:text-[10px]">
												The integration can only access pages that have been explicitly shared with
												it. Make sure to share all pages you want to index.
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
										Navigate to the Connector Dashboard and select the <strong>Notion</strong>{" "}
										Connector.
									</li>
									<li>
										Place the <strong>Integration Token</strong> in the form field.
									</li>
									<li>
										Click <strong>Connect</strong> to establish the connection.
									</li>
									<li>Once connected, your Notion pages will be indexed automatically.</li>
								</ol>

								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">What Gets Indexed</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										<p className="mb-2">The Notion connector indexes the following data:</p>
										<ul className="list-disc pl-5 space-y-1">
											<li>Page titles and content</li>
											<li>Database entries and properties</li>
											<li>Page metadata and properties</li>
											<li>Nested pages and sub-pages</li>
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
