"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
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
				<Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0 ml-1 text-purple-500" />
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
		</div>
	);
};
