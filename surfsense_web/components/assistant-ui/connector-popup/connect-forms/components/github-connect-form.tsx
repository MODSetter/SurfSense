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
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const githubConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	github_pat: z
		.string()
		.optional()
		.refine(
			(pat) => !pat || pat.startsWith("ghp_") || pat.startsWith("github_pat_"),
			{
				message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
			}
		),
	repo_full_names: z.string().min(1, {
		message: "At least one repository is required.",
	}),
});

type GithubConnectorFormValues = z.infer<typeof githubConnectorFormSchema>;

export const GithubConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
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
					GITHUB_PAT: values.github_pat || null, // Optional - only for private repos
					repo_full_names: repoList,
				},
				is_indexable: true,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: periodicEnabled,
				indexing_frequency_minutes: periodicEnabled ? parseInt(frequencyMinutes, 10) : null,
				next_scheduled_at: null,
				// GitHub indexes full repo snapshots - no date range needed
				startDate: undefined,
				endDate: undefined,
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
					<AlertTitle className="text-xs sm:text-sm">Personal Access Token (Optional)</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						A GitHub PAT is only required for private repositories. Public repos work without a
						token. {" "}
						<a
							href="https://github.com/settings/tokens/new?description=surfsense&scopes=repo"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							Get your token
						</a>{" "}
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
									<FormLabel className="text-xs sm:text-sm">
										GitHub Personal Access Token{" "}
										<span className="text-muted-foreground font-normal">(optional)</span>
									</FormLabel>
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
										Only required for private repositories. Leave empty if indexing public repos
										only.
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
							<h3 className="text-sm sm:text-base font-medium">Sync Configuration</h3>

							{/* Note: No date range for GitHub - it indexes full repo snapshots */}

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
								The GitHub connector ingests entire repositories in one pass using gitingest,
								making it highly efficient. Provide a comma-separated list of repository full
								names (e.g., "owner/repo1, owner/repo2") to index.
							</p>
							<ul className="mt-2 list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
								<li>
									<strong>Public repos:</strong> No authentication required.
								</li>
								<li>
									<strong>Private repos:</strong> Requires a GitHub Personal Access Token (PAT).
								</li>
								<li>Indexes code, documentation, and configuration files.</li>
								<li>Large files (over 5MB) and binary files are automatically skipped.</li>
								<li>
									Periodic sync detects changes and only re-indexes when content has changed.
								</li>
							</ul>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">Authorization</h3>
								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 mb-4">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">
										Personal Access Token (Optional)
									</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										A GitHub PAT is only needed for <strong>private repositories</strong>. Public
										repos can be indexed without authentication. If you need to access private
										repos, create a PAT with the 'repo' scope.
									</AlertDescription>
								</Alert>

								<div className="space-y-4 sm:space-y-6">
									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											For Private Repositories Only: Generate GitHub PAT
										</h4>
										<p className="text-[10px] sm:text-xs text-muted-foreground mb-2">
											Skip this step if you're only indexing public repositories.
										</p>
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
												<strong>Tokens (classic)</strong> or <strong>Fine-grained tokens</strong>.
											</li>
											<li>
												Click <strong>Generate new token</strong>.
											</li>
											<li>Give your token a descriptive name (e.g., "SurfSense Connector").</li>
											<li>
												Grant the <strong>`repo`</strong> scope (for classic tokens) or read access
												to the specific repositories you want to index (for fine-grained tokens).
											</li>
											<li>
												Click <strong>Generate token</strong> and copy it immediately.
											</li>
										</ol>
									</div>

									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Specify Repositories
										</h4>
										<p className="text-[10px] sm:text-xs text-muted-foreground mb-3">
											Enter a comma-separated list of repository full names in the format
											"owner/repo1, owner/repo2". For example: "facebook/react, vercel/next.js".
										</p>
										<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
											<Info className="h-3 w-3 sm:h-4 sm:w-4" />
											<AlertTitle className="text-[10px] sm:text-xs">Public vs Private</AlertTitle>
											<AlertDescription className="text-[9px] sm:text-[10px]">
												Public repositories work without a PAT. For private repositories, ensure
												your PAT has access to the repos you want to index.
											</AlertDescription>
										</Alert>
									</div>
								</div>
							</div>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">Quick Start</h3>
								<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground mb-4">
									<li>
										Enter the <strong>Repository Names</strong> you want to index (e.g.,
										"facebook/react, vercel/next.js").
									</li>
									<li>
										<strong>(Optional)</strong> Add a GitHub PAT if indexing private repositories.
									</li>
									<li>
										Click <strong>Connect GitHub</strong> to start indexing.
									</li>
									<li>
										Enable <strong>Periodic Sync</strong> to automatically detect and index
										changes.
									</li>
								</ol>

								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">What Gets Indexed</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										<p className="mb-2">The GitHub connector indexes:</p>
										<ul className="list-disc pl-5 space-y-1">
											<li>All code files (Python, JavaScript, TypeScript, etc.)</li>
											<li>Documentation (README, Markdown, text files)</li>
											<li>Configuration files (JSON, YAML, TOML, etc.)</li>
											<li>Repository structure and file tree</li>
										</ul>
										<p className="mt-2">
											Binary files, images, and build artifacts are automatically excluded.
										</p>
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
