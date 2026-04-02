"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FolderSync, Info } from "lucide-react";
import type { FC } from "react";
import { useRef } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const localFolderFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	folder_path: z.string().min(1, {
		message: "Folder path is required.",
	}),
	folder_name: z.string().min(1, {
		message: "Folder name is required.",
	}),
	exclude_patterns: z.string().optional(),
	file_extensions: z.string().optional(),
});

type LocalFolderFormValues = z.infer<typeof localFolderFormSchema>;

export const LocalFolderConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const isElectron = typeof window !== "undefined" && !!window.electronAPI;

	const form = useForm<LocalFolderFormValues>({
		resolver: zodResolver(localFolderFormSchema),
		defaultValues: {
			name: "Local Folder",
			folder_path: "",
			folder_name: "",
			exclude_patterns: "node_modules,.git,.DS_Store",
			file_extensions: "",
		},
	});

	const handleBrowse = async () => {
		if (!isElectron) return;
		const selected = await window.electronAPI!.selectFolder();
		if (selected) {
			form.setValue("folder_path", selected);
			const folderName = selected.split(/[\\/]/).pop() || "folder";
			if (!form.getValues("folder_name")) {
				form.setValue("folder_name", folderName);
			}
			if (form.getValues("name") === "Local Folder") {
				form.setValue("name", folderName);
			}
		}
	};

	const handleSubmit = async (values: LocalFolderFormValues) => {
		if (isSubmittingRef.current || isSubmitting) return;
		isSubmittingRef.current = true;

		try {
			const excludePatterns = values.exclude_patterns
				? values.exclude_patterns
						.split(",")
						.map((p) => p.trim())
						.filter(Boolean)
				: [];

			const fileExtensions = values.file_extensions
				? values.file_extensions
						.split(",")
						.map((e) => {
							const ext = e.trim();
							return ext.startsWith(".") ? ext : `.${ext}`;
						})
						.filter(Boolean)
				: null;

			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.LOCAL_FOLDER_CONNECTOR,
				config: {
					folder_path: values.folder_path,
					folder_name: values.folder_name,
					exclude_patterns: excludePatterns,
					file_extensions: fileExtensions,
				},
				is_indexable: true,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: false,
				indexing_frequency_minutes: null,
				next_scheduled_at: null,
			});
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert className="bg-blue-500/10 dark:bg-blue-500/10 border-blue-500/30 p-2 sm:p-3">
				<Info className="size-4 shrink-0 text-blue-500" />
				<AlertTitle className="text-xs sm:text-sm">Desktop App Required</AlertTitle>
				<AlertDescription className="text-[10px] sm:text-xs">
					Real-time file watching is powered by the SurfSense desktop app. Files are
					automatically synced whenever changes are detected.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="local-folder-connect-form"
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
											placeholder="My Documents"
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
							name="folder_path"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Folder Path</FormLabel>
									<div className="flex gap-2">
										<FormControl>
											<Input
												placeholder="/path/to/your/folder"
												className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono flex-1"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										{isElectron && (
											<Button
												type="button"
												variant="outline"
												size="sm"
												onClick={handleBrowse}
												disabled={isSubmitting}
												className="shrink-0"
											>
												<FolderSync className="h-4 w-4 mr-1" />
												Browse
											</Button>
										)}
									</div>
									<FormDescription className="text-[10px] sm:text-xs">
										The absolute path to the folder to watch and sync.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="folder_name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Display Name</FormLabel>
									<FormControl>
										<Input
											placeholder="My Notes"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										A friendly name shown in the documents sidebar.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="exclude_patterns"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Exclude Patterns</FormLabel>
									<FormControl>
										<Input
											placeholder="node_modules,.git,.DS_Store"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Comma-separated patterns of directories/files to exclude.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="file_extensions"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">File Extensions (optional)</FormLabel>
									<FormControl>
										<Input
											placeholder=".md,.txt,.rst"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Leave empty to index all supported files, or specify comma-separated extensions.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

					</form>
				</Form>
			</div>

			{getConnectorBenefits(EnumConnectorName.LOCAL_FOLDER_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">
						What you get with Local Folder sync:
					</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.LOCAL_FOLDER_CONNECTOR)?.map(
							(benefit) => <li key={benefit}>{benefit}</li>
						)}
					</ul>
				</div>
			)}
		</div>
	);
};
