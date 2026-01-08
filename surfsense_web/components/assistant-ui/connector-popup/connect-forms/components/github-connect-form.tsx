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

const githubConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	github_pat: z
		.string()
		.min(20, {
			message: "GitHub Personal Access Token seems too short.",
		})
		.refine((pat) => pat.startsWith("ghp_") || pat.startsWith("github_pat_"), {
			message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
		}),
	repo_full_names: z.string().min(1, {
		message: "At least one repository is required.",
	}),
});

type GithubConnectorFormValues = z.infer<typeof githubConnectorFormSchema>;

export const GithubConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const form = useForm<GithubConnectorFormValues>({
		resolver: zodResolver(githubConnectorFormSchema),
		defaultValues: {
			name: "GitHub Connector",
			github_pat: "",
			repo_full_names: "",
		},
	});

	const stringToArray = (str: string): string[] => {
		const items = str
			.split(",")
			.map((item) => item.trim())
			.filter((item) => item.length > 0);
		return Array.from(new Set(items));
	};

	const handleSubmit = async (values: GithubConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			const repoList = stringToArray(values.repo_full_names);

			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.GITHUB_CONNECTOR,
				config: {
					GITHUB_PAT: values.github_pat,
					repo_full_names: repoList,
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
					<AlertTitle className="text-xs sm:text-sm">Personal Access Token Required</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						You'll need a GitHub Personal Access Token to use this connector. You can create one
						from{" "}
						<a
							href="https://github.com/settings/tokens"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							GitHub Settings
						</a>
					</AlertDescription>
				</div>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="github-connect-form"
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
											placeholder="My GitHub Connector"
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
							name="github_pat"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">GitHub Personal Access Token</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder="ghp_..."
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Your GitHub PAT will be encrypted and stored securely. It typically starts with
										"ghp_" or "github_pat_".
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="repo_full_names"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Repository Names</FormLabel>
									<FormControl>
										<Input
											placeholder="owner/repo1, owner/repo2"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Comma-separated list of repository full names (e.g., "owner/repo1,
										owner/repo2").
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Show parsed repositories as badges */}
						{form.watch("repo_full_names")?.trim() && (
							<div className="rounded-lg border border-border bg-muted/50 p-3">
								<h4 className="text-[10px] sm:text-xs font-medium mb-2">Selected Repositories:</h4>
								<div className="flex flex-wrap gap-2">
									{stringToArray(form.watch("repo_full_names") ?? "").map((repo) => (
										<Badge key={repo} variant="secondary" className="text-[10px]">
											{repo}
										</Badge>
									))}
								</div>
							</div>
						)}

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
			{getConnectorBenefits(EnumConnectorName.GITHUB_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">What you get with GitHub integration:</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.GITHUB_CONNECTOR)?.map((benefit) => (
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
								The GitHub connector uses a Personal Access Token (PAT) to authenticate with the
								GitHub API. You provide a comma-separated list of repository full names (e.g.,
								"owner/repo1, owner/repo2") that you want to index. The connector indexes relevant
								files (code, markdown, text) from the selected repositories.
							</p>
							<ul className="mt-2 list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
								<li>
									The connector indexes files based on common code and documentation extensions.
								</li>
								<li>Large files (over 1MB) are skipped during indexing.</li>
								<li>Only specified repositories are indexed.</li>
								<li>
									Indexing runs periodically (check connector settings for frequency) to keep
									content up-to-date.
								</li>
							</ul>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">Authorization</h3>
								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 mb-4">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">
										Personal Access Token Required
									</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										You'll need a GitHub PAT with the appropriate scopes (e.g., 'repo') to fetch
										repositories. The PAT will be stored securely to enable indexing.
									</AlertDescription>
								</Alert>

								<div className="space-y-4 sm:space-y-6">
									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 1: Generate GitHub PAT
										</h4>
										<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground">
											<li>
												Go to your GitHub{" "}
												<a
													href="https://github.com/settings/tokens"
													target="_blank"
													rel="noopener noreferrer"
													className="font-medium underline underline-offset-4"
												>
													Developer settings
												</a>
											</li>
											<li>
												Click on <strong>Personal access tokens</strong>, then choose{" "}
												<strong>Tokens (classic)</strong> or <strong>Fine-grained tokens</strong>{" "}
												(recommended if available).
											</li>
											<li>
												Click <strong>Generate new token</strong> (and choose the appropriate type).
											</li>
											<li>Give your token a descriptive name (e.g., "SurfSense Connector").</li>
											<li>Set an expiration date for the token (recommended for security).</li>
											<li>
												Under <strong>Select scopes</strong> (for classic tokens) or{" "}
												<strong>Repository access</strong> (for fine-grained), grant the necessary
												permissions. At minimum, the <strong>`repo`</strong> scope (or equivalent
												read access to repositories for fine-grained tokens) is required to read
												repository content.
											</li>
											<li>
												Click <strong>Generate token</strong>.
											</li>
											<li>
												<strong>Important:</strong> Copy your new PAT immediately. You won't be able
												to see it again after leaving the page.
											</li>
										</ol>
									</div>

									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 2: Specify repositories
										</h4>
										<p className="text-[10px] sm:text-xs text-muted-foreground mb-3">
											Enter a comma-separated list of repository full names in the format
											"owner/repo1, owner/repo2". The connector will index files from only the
											specified repositories.
										</p>
										<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
											<Info className="h-3 w-3 sm:h-4 sm:w-4" />
											<AlertTitle className="text-[10px] sm:text-xs">Repository Access</AlertTitle>
											<AlertDescription className="text-[9px] sm:text-[10px]">
												Make sure your PAT has access to all repositories you want to index. Private
												repositories require appropriate permissions.
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
										Navigate to the Connector Dashboard and select the <strong>GitHub</strong>{" "}
										Connector.
									</li>
									<li>
										Enter your <strong>GitHub Personal Access Token</strong> in the form field.
									</li>
									<li>
										Enter a comma-separated list of <strong>Repository Names</strong> (e.g.,
										"owner/repo1, owner/repo2").
									</li>
									<li>
										Click <strong>Connect</strong> to establish the connection.
									</li>
									<li>Once connected, your GitHub repositories will be indexed automatically.</li>
								</ol>

								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">What Gets Indexed</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										<p className="mb-2">The GitHub connector indexes the following data:</p>
										<ul className="list-disc pl-5 space-y-1">
											<li>Code files from selected repositories</li>
											<li>README files and Markdown documentation</li>
											<li>Common text-based file formats</li>
											<li>Repository metadata and structure</li>
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
