"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ExternalLink, Info } from "lucide-react";
import Link from "next/link";
import type { FC } from "react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
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
import type { ConnectFormProps } from "../index";

const githubConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	github_pat: z
		.string()
		.optional()
		.refine((pat) => !pat || pat.startsWith("ghp_") || pat.startsWith("github_pat_"), {
			message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
		}),
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
						token.{" "}
						<a
							href="https://github.com/settings/tokens/new?description=surfsense&scopes=repo"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4 inline-flex items-center gap-1.5"
						>
							Get your token
							<ExternalLink className="h-3 w-3 sm:h-4 sm:w-4" />
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

			{/* Documentation Link */}
			<div>
				<Link
					href="/docs/connectors/github"
					target="_blank"
					rel="noopener noreferrer"
					className="text-xs sm:text-sm font-medium underline underline-offset-4 hover:text-primary transition-colors inline-flex items-center gap-1.5"
				>
					View GitHub Connector Documentation
					<ExternalLink className="h-3 w-3 sm:h-4 sm:w-4" />
				</Link>
			</div>
		</div>
	);
};
