"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FolderOpen, Info } from "lucide-react";
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
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const obsidianConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	vault_path: z.string().min(1, {
		message: "Vault path is required.",
	}),
	vault_name: z.string().min(1, {
		message: "Vault name is required.",
	}),
	exclude_folders: z.string().optional(),
	include_attachments: z.boolean(),
});

type ObsidianConnectorFormValues = z.infer<typeof obsidianConnectorFormSchema>;

export const ObsidianConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [periodicEnabled, setPeriodicEnabled] = useState(true);
	const [frequencyMinutes, setFrequencyMinutes] = useState("60");
	const form = useForm<ObsidianConnectorFormValues>({
		resolver: zodResolver(obsidianConnectorFormSchema),
		defaultValues: {
			name: "Obsidian Vault",
			vault_path: "",
			vault_name: "",
			exclude_folders: ".obsidian,.trash",
			include_attachments: false,
		},
	});

	const handleSubmit = async (values: ObsidianConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			// Parse exclude_folders into an array
			const excludeFolders = values.exclude_folders
				? values.exclude_folders
						.split(",")
						.map((f) => f.trim())
						.filter(Boolean)
				: [".obsidian", ".trash"];

			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.OBSIDIAN_CONNECTOR,
				config: {
					vault_path: values.vault_path,
					vault_name: values.vault_name,
					exclude_folders: excludeFolders,
					include_attachments: values.include_attachments,
				},
				is_indexable: true,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: periodicEnabled,
				indexing_frequency_minutes: periodicEnabled ? Number.parseInt(frequencyMinutes, 10) : null,
				next_scheduled_at: null,
				periodicEnabled,
				frequencyMinutes,
			});
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert className="bg-purple-500/10 dark:bg-purple-500/10 border-purple-500/30 p-2 sm:p-3 flex items-center [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
				<FolderOpen className="h-3 w-3 sm:h-4 sm:w-4 shrink-0 ml-1 text-purple-500" />
				<div className="-ml-1">
					<AlertTitle className="text-xs sm:text-sm">Self-Hosted Only</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs pl-0!">
						This connector requires direct file system access and only works with self-hosted
						SurfSense installations.
					</AlertDescription>
				</div>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="obsidian-connect-form"
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
											placeholder="My Obsidian Vault"
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
							name="vault_path"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Vault Path</FormLabel>
									<FormControl>
										<Input
											placeholder="/path/to/your/obsidian/vault"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										The absolute path to your Obsidian vault on the server. This must be accessible
										from the SurfSense backend.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="vault_name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Vault Name</FormLabel>
									<FormControl>
										<Input
											placeholder="My Knowledge Base"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										A display name for your vault. This will be used in search results.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="exclude_folders"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Exclude Folders</FormLabel>
									<FormControl>
										<Input
											placeholder=".obsidian,.trash,templates"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Comma-separated list of folder names to exclude from indexing.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="include_attachments"
							render={({ field }) => (
								<FormItem className="flex flex-row items-center justify-between rounded-lg border border-slate-400/20 p-3">
									<div className="space-y-0.5">
										<FormLabel className="text-xs sm:text-sm">Include Attachments</FormLabel>
										<FormDescription className="text-[10px] sm:text-xs">
											Index attachment folders and embedded files (images, PDFs, etc.)
										</FormDescription>
									</div>
									<FormControl>
										<Switch
											checked={field.value}
											onCheckedChange={field.onChange}
											disabled={isSubmitting}
										/>
									</FormControl>
								</FormItem>
							)}
						/>

						{/* Indexing Configuration */}
						<div className="space-y-4 pt-4 border-t border-slate-400/20">
							<h3 className="text-sm sm:text-base font-medium">Indexing Configuration</h3>

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
												<SelectContent className="z-100">
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
			{getConnectorBenefits(EnumConnectorName.OBSIDIAN_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">
						What you get with Obsidian integration:
					</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.OBSIDIAN_CONNECTOR)?.map((benefit) => (
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
								The Obsidian connector scans your local Obsidian vault directory and indexes all
								Markdown files. It preserves your note structure and extracts metadata from YAML
								frontmatter.
							</p>
							<ul className="mt-2 list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
								<li>
									The connector parses frontmatter metadata (title, tags, aliases, dates, etc.)
								</li>
								<li>Wiki-style links ([[note]]) are extracted and preserved</li>
								<li>Inline tags (#tag) are recognized and indexed</li>
								<li>Content is chunked intelligently for optimal search results</li>
								<li>
									Subsequent indexing runs use content hashing to skip unchanged files for faster
									sync
								</li>
							</ul>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">Setup</h3>
								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 mb-4">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">
										File System Access Required
									</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										The SurfSense backend must have read access to your Obsidian vault directory.
										For Docker deployments, mount your vault as a volume.
									</AlertDescription>
								</Alert>

								<div className="space-y-4 sm:space-y-6">
									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 1: Locate your vault
										</h4>
										<ol className="list-decimal pl-5 space-y-2 text-[10px] sm:text-xs text-muted-foreground">
											<li>
												<strong>macOS/Linux:</strong> Right-click any note in Obsidian → "Reveal in
												Finder" to see the vault folder
											</li>
											<li>
												<strong>Windows:</strong> Right-click any note → "Show in system explorer"
											</li>
											<li>
												<strong>Or:</strong> Click the vault switcher (bottom-left icon) → "Open
												folder" next to your vault name
											</li>
										</ol>
									</div>

									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 2: Enter the path
										</h4>
										<p className="text-[10px] sm:text-xs text-muted-foreground mb-2">
											<strong>Running locally (no Docker):</strong> Use the direct path to your
											vault:
										</p>
										<pre className="bg-slate-800 text-slate-200 p-2 rounded text-[9px] sm:text-[10px] overflow-x-auto mb-2">
											{`/Users/yourname/Documents/MyObsidianVault`}
										</pre>
										<p className="text-[10px] sm:text-xs text-muted-foreground mb-2">
											<strong>Running in Docker:</strong> Mount your vault as a volume in
											docker-compose.yml:
										</p>
										<pre className="bg-slate-800 text-slate-200 p-2 rounded text-[9px] sm:text-[10px] overflow-x-auto">
											{`volumes:
  - /path/to/your/vault:/app/obsidian_vaults/my-vault:ro`}
										</pre>
										<p className="text-[10px] sm:text-xs text-muted-foreground mt-2">
											Then use <code>/app/obsidian_vaults/my-vault</code> as your vault path.
										</p>
									</div>

									<div>
										<h4 className="text-[10px] sm:text-xs font-medium mb-2">
											Step 3: Configure exclusions
										</h4>
										<p className="text-[10px] sm:text-xs text-muted-foreground">
											Common folders to exclude:
										</p>
										<ul className="list-disc pl-5 mt-1 space-y-1 text-[10px] sm:text-xs text-muted-foreground">
											<li>
												<code>.obsidian</code> - Obsidian config (always recommended)
											</li>
											<li>
												<code>.trash</code> - Obsidian's trash folder
											</li>
											<li>
												<code>templates</code> - If you have a templates folder
											</li>
											<li>
												<code>daily-notes</code> - If you want to exclude daily notes
											</li>
										</ul>
									</div>
								</div>
							</div>
						</div>

						<div className="space-y-4">
							<div>
								<h3 className="text-sm sm:text-base font-semibold mb-2">What Gets Indexed</h3>
								<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
									<Info className="h-3 w-3 sm:h-4 sm:w-4" />
									<AlertTitle className="text-[10px] sm:text-xs">Indexed Content</AlertTitle>
									<AlertDescription className="text-[9px] sm:text-[10px]">
										<p className="mb-2">The Obsidian connector indexes:</p>
										<ul className="list-disc pl-5 space-y-1">
											<li>All Markdown files (.md) in your vault</li>
											<li>YAML frontmatter metadata (title, tags, aliases, dates)</li>
											<li>Wiki-style links between notes</li>
											<li>Inline tags throughout your notes</li>
											<li>Full note content with proper chunking</li>
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
