"use client";

import { Mail, Tag } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

interface ComposioGmailConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

interface GmailIndexingOptions {
	max_emails: number;
	label_filter: string;
	search_query: string;
}

const DEFAULT_GMAIL_OPTIONS: GmailIndexingOptions = {
	max_emails: 500,
	label_filter: "",
	search_query: "",
};

export const ComposioGmailConfig: FC<ComposioGmailConfigProps> = ({ connector, onConfigChange }) => {
	const isIndexable = connector.config?.is_indexable as boolean;

	// Initialize with existing options from connector config
	const existingOptions =
		(connector.config?.gmail_options as GmailIndexingOptions | undefined) || DEFAULT_GMAIL_OPTIONS;

	const [gmailOptions, setGmailOptions] = useState<GmailIndexingOptions>(existingOptions);

	// Update options when connector config changes
	useEffect(() => {
		const options =
			(connector.config?.gmail_options as GmailIndexingOptions | undefined) ||
			DEFAULT_GMAIL_OPTIONS;
		setGmailOptions(options);
	}, [connector.config]);

	const updateConfig = (options: GmailIndexingOptions) => {
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				gmail_options: options,
			});
		}
	};

	const handleOptionChange = (key: keyof GmailIndexingOptions, value: number | string) => {
		const newOptions = { ...gmailOptions, [key]: value };
		setGmailOptions(newOptions);
		updateConfig(newOptions);
	};

	// Only show configuration if the connector is indexable
	if (!isIndexable) {
		return <div className="space-y-6" />;
	}

	return (
		<div className="space-y-6">
			{/* Gmail Indexing Options */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<div className="flex items-center gap-2">
						<Mail className="size-4 text-red-500" />
						<h3 className="font-medium text-sm sm:text-base">Gmail Indexing Options</h3>
					</div>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Configure how emails are indexed from your Gmail account.
					</p>
				</div>

				{/* Max emails to index */}
				<div className="space-y-2">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="max-emails" className="text-sm font-medium">
								Max emails to index
							</Label>
							<p className="text-xs text-muted-foreground">
								Maximum number of emails to index per sync
							</p>
						</div>
						<Select
							value={gmailOptions.max_emails.toString()}
							onValueChange={(value) =>
								handleOptionChange("max_emails", parseInt(value, 10))
							}
						>
							<SelectTrigger
								id="max-emails"
								className="w-[140px] bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder="Select limit" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="100" className="text-xs sm:text-sm">
									100 emails
								</SelectItem>
								<SelectItem value="250" className="text-xs sm:text-sm">
									250 emails
								</SelectItem>
								<SelectItem value="500" className="text-xs sm:text-sm">
									500 emails
								</SelectItem>
								<SelectItem value="1000" className="text-xs sm:text-sm">
									1000 emails
								</SelectItem>
								<SelectItem value="2500" className="text-xs sm:text-sm">
									2500 emails
								</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>

				{/* Label filter */}
				<div className="space-y-2 pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<div className="flex items-center gap-1.5">
							<Tag className="size-3.5 text-muted-foreground" />
							<Label htmlFor="label-filter" className="text-sm font-medium">
								Label filter (optional)
							</Label>
						</div>
						<p className="text-xs text-muted-foreground">
							Only index emails with this label (e.g., "INBOX", "IMPORTANT", "work")
						</p>
					</div>
					<Input
						id="label-filter"
						value={gmailOptions.label_filter}
						onChange={(e) => handleOptionChange("label_filter", e.target.value)}
						placeholder="Enter label name..."
						className="bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
					/>
				</div>

				{/* Search query */}
				<div className="space-y-2 pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="search-query" className="text-sm font-medium">
							Search query (optional)
						</Label>
						<p className="text-xs text-muted-foreground">
							Gmail search query to filter emails (e.g., "from:boss@company.com", "has:attachment")
						</p>
					</div>
					<Input
						id="search-query"
						value={gmailOptions.search_query}
						onChange={(e) => handleOptionChange("search_query", e.target.value)}
						placeholder="Enter Gmail search query..."
						className="bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
					/>
				</div>
			</div>
		</div>
	);
};

