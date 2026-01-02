"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useRef } from "react";
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
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const searxngFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	host: z
		.string()
		.min(1, { message: "Host is required." })
		.url({ message: "Enter a valid SearxNG host URL (e.g. https://searxng.example.org)." }),
	api_key: z.string().optional(),
	engines: z.string().optional(),
	categories: z.string().optional(),
	language: z.string().optional(),
	safesearch: z
		.string()
		.regex(/^[0-2]?$/, { message: "SafeSearch must be 0, 1, or 2." })
		.optional(),
	verify_ssl: z.boolean(),
});

type SearxngFormValues = z.infer<typeof searxngFormSchema>;

const parseCommaSeparated = (value?: string | null) => {
	if (!value) return undefined;
	const items = value
		.split(",")
		.map((item) => item.trim())
		.filter((item) => item.length > 0);
	return items.length > 0 ? items : undefined;
};

export const SearxngConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const form = useForm<SearxngFormValues>({
		resolver: zodResolver(searxngFormSchema),
		defaultValues: {
			name: "SearxNG Connector",
			host: "",
			api_key: "",
			engines: "",
			categories: "",
			language: "",
			safesearch: "",
			verify_ssl: true,
		},
	});

	const handleSubmit = async (values: SearxngFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			const config: Record<string, unknown> = {
				SEARXNG_HOST: values.host.trim(),
			};

			const apiKey = values.api_key?.trim();
			if (apiKey) config.SEARXNG_API_KEY = apiKey;

			const engines = parseCommaSeparated(values.engines);
			if (engines) config.SEARXNG_ENGINES = engines;

			const categories = parseCommaSeparated(values.categories);
			if (categories) config.SEARXNG_CATEGORIES = categories;

			const language = values.language?.trim();
			if (language) config.SEARXNG_LANGUAGE = language;

			const safesearch = values.safesearch?.trim();
			if (safesearch) {
				const parsed = Number(safesearch);
				if (!Number.isNaN(parsed)) {
					config.SEARXNG_SAFESEARCH = parsed;
				}
			}

			// Include verify flag only when disabled to keep config minimal
			if (values.verify_ssl === false) {
				config.SEARXNG_VERIFY_SSL = false;
			}

			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.SEARXNG_API,
				config,
				is_indexable: false,
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
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-center [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
				<Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0 ml-1" />
				<div className="-ml-1">
					<AlertTitle className="text-xs sm:text-sm">SearxNG Instance Required</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						You need access to a running SearxNG instance. Refer to the{" "}
						<a
							href="https://docs.searxng.org/admin/installation-docker.html"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							SearxNG installation guide
						</a>{" "}
						for setup instructions. If your instance requires an API key, include it below.
					</AlertDescription>
				</div>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="searxng-connect-form"
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
											placeholder="My SearxNG Connector"
											className="border-slate-400/20 focus-visible:border-slate-400/40"
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
							name="host"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">SearxNG Host</FormLabel>
									<FormControl>
										<Input
											placeholder="https://searxng.example.org"
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Provide the full base URL to your SearxNG instance. Include the protocol
										(http/https).
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="api_key"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">API Key (optional)</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder="Enter API key if your instance requires one"
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Leave empty if your SearxNG instance does not enforce API keys.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
							<FormField
								control={form.control}
								name="engines"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">Engines (optional)</FormLabel>
										<FormControl>
											<Input
												placeholder="google,bing,duckduckgo"
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											Comma-separated list to target specific engines.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="categories"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">Categories (optional)</FormLabel>
										<FormControl>
											<Input
												placeholder="general,it,science"
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											Comma-separated list of SearxNG categories.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
							<FormField
								control={form.control}
								name="language"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">
											Preferred Language (optional)
										</FormLabel>
										<FormControl>
											<Input
												placeholder="en-US"
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											IETF language tag (e.g. en, en-US). Leave blank to inherit defaults.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="safesearch"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">
											SafeSearch Level (optional)
										</FormLabel>
										<FormControl>
											<Input
												placeholder="0 (off), 1 (moderate), 2 (strict)"
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											Set 0, 1, or 2 to adjust SafeSearch filtering. Leave blank to use the instance
											default.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<FormField
							control={form.control}
							name="verify_ssl"
							render={({ field }) => (
								<FormItem className="flex items-center justify-between rounded-lg border border-slate-400/20 p-3 sm:p-4">
									<div>
										<FormLabel className="text-xs sm:text-sm">Verify SSL Certificates</FormLabel>
										<FormDescription className="text-[10px] sm:text-xs">
											Disable only when connecting to instances with self-signed certificates.
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
					</form>
				</Form>
			</div>

			{/* What you get section */}
			{getConnectorBenefits(EnumConnectorName.SEARXNG_API) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">What you get with SearxNG:</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.SEARXNG_API)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
};
