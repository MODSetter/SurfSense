"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info, Loader2, RefreshCw, X } from "lucide-react";
import type { FC } from "react";
import { useCallback, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { DateRangeSelector } from "../../components/date-range-selector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const bookstackConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	base_url: z.string().url({ message: "Please enter a valid BookStack base URL." }),
	token_id: z.string().min(1, {
		message: "BookStack Token ID is required.",
	}),
	token_secret: z.string().min(1, {
		message: "BookStack Token Secret is required.",
	}),
});

type BookStackConnectorFormValues = z.infer<typeof bookstackConnectorFormSchema>;

interface BookStackShelf {
	id: number;
	name: string;
	book_count: number;
	books: { id: number; name: string }[];
}

export const BookStackConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const isSubmittingRef = useRef(false);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const [shelves, setShelves] = useState<BookStackShelf[]>([]);
	const [excludedShelfIds, setExcludedShelfIds] = useState<number[]>([]);
	const [loadingShelves, setLoadingShelves] = useState(false);
	const [shelvesError, setShelvesError] = useState<string | null>(null);
	const [shelvesLoaded, setShelvesLoaded] = useState(false);

	const form = useForm<BookStackConnectorFormValues>({
		resolver: zodResolver(bookstackConnectorFormSchema),
		defaultValues: {
			name: "BookStack Connector",
			base_url: "",
			token_id: "",
			token_secret: "",
		},
	});

	const fetchShelves = useCallback(async () => {
		const values = form.getValues();
		if (!values.base_url || !values.token_id || !values.token_secret) {
			setShelvesError("Please fill in Base URL, Token ID, and Token Secret first.");
			return;
		}

		setLoadingShelves(true);
		setShelvesError(null);

		try {
			const data = await connectorsApiService.listBookStackShelves(
				values.base_url,
				values.token_id,
				values.token_secret,
			) as BookStackShelf[];
			setShelves(data);
			setShelvesLoaded(true);
		} catch (err) {
			setShelvesError(err instanceof Error ? err.message : "Failed to fetch shelves");
			setShelves([]);
			setShelvesLoaded(false);
		} finally {
			setLoadingShelves(false);
		}
	}, [form]);

	const toggleShelfExclusion = (shelfId: number) => {
		setExcludedShelfIds((prev) =>
			prev.includes(shelfId)
				? prev.filter((id) => id !== shelfId)
				: [...prev, shelfId]
		);
	};

	const handleSubmit = async (values: BookStackConnectorFormValues) => {
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.BOOKSTACK_CONNECTOR,
				config: {
					BOOKSTACK_BASE_URL: values.base_url,
					BOOKSTACK_TOKEN_ID: values.token_id,
					BOOKSTACK_TOKEN_SECRET: values.token_secret,
					BOOKSTACK_EXCLUDED_SHELF_IDS: excludedShelfIds,
				},
				is_indexable: true,
				is_active: true,
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
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3">
				<Info className="size-4 shrink-0" />
				<AlertTitle className="text-xs sm:text-sm">API Token Required</AlertTitle>
				<AlertDescription className="text-[10px] sm:text-xs">
					You'll need a BookStack API Token to use this connector. You can create one from your
					BookStack instance settings.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="bookstack-connect-form"
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
											placeholder="My BookStack Connector"
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
									<FormLabel className="text-xs sm:text-sm">BookStack Base URL</FormLabel>
									<FormControl>
										<Input
											type="url"
											placeholder="https://your-bookstack-instance.com"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										The base URL of your BookStack instance (e.g.,
										https://your-bookstack-instance.com).
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="token_id"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Token ID</FormLabel>
									<FormControl>
										<Input
											placeholder="Your Token ID"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Your BookStack API Token ID.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="token_secret"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Token Secret</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder="Your Token Secret"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Your BookStack API Token Secret will be encrypted and stored securely.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Shelf Exclusion Picker */}
						<div className="space-y-3 pt-4 border-t border-slate-400/20">
							<div className="flex items-center justify-between">
								<div>
									<h3 className="text-sm sm:text-base font-medium">Shelf Filter</h3>
									<p className="text-[10px] sm:text-xs text-muted-foreground mt-1">
										Optionally exclude shelves from indexing. Click &quot;Load Shelves&quot; after entering your credentials.
									</p>
								</div>
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={fetchShelves}
									disabled={loadingShelves || isSubmitting}
									className="text-xs"
								>
									{loadingShelves ? (
										<Loader2 className="h-3 w-3 animate-spin mr-1" />
									) : (
										<RefreshCw className="h-3 w-3 mr-1" />
									)}
									{shelvesLoaded ? "Refresh" : "Load Shelves"}
								</Button>
							</div>

							{shelvesError && (
								<p className="text-xs text-destructive">{shelvesError}</p>
							)}

							{shelvesLoaded && shelves.length > 0 && (
								<div className="rounded-lg border border-slate-400/20 divide-y divide-slate-400/10">
									{shelves.map((shelf) => {
										const isExcluded = excludedShelfIds.includes(shelf.id);
										return (
											<label
												key={shelf.id}
												className={`flex items-center gap-3 p-2.5 sm:p-3 cursor-pointer hover:bg-slate-400/5 transition-colors ${
													isExcluded ? "opacity-50" : ""
												}`}
											>
												<Checkbox
													checked={!isExcluded}
													onCheckedChange={() => toggleShelfExclusion(shelf.id)}
												/>
												<div className="flex-1 min-w-0">
													<div className="text-xs sm:text-sm font-medium truncate">
														{shelf.name}
													</div>
													<div className="text-[10px] sm:text-xs text-muted-foreground">
														{shelf.book_count} {shelf.book_count === 1 ? "book" : "books"}
													</div>
												</div>
												{isExcluded && (
													<Badge variant="secondary" className="text-[10px] shrink-0">
														Excluded
													</Badge>
												)}
											</label>
										);
									})}
								</div>
							)}

							{shelvesLoaded && shelves.length === 0 && (
								<p className="text-xs text-muted-foreground italic">No shelves found in this BookStack instance.</p>
							)}

							{excludedShelfIds.length > 0 && shelvesLoaded && (
								<div className="flex flex-wrap gap-1.5 mt-2">
									<span className="text-[10px] sm:text-xs text-muted-foreground">Excluding:</span>
									{excludedShelfIds.map((id) => {
										const shelf = shelves.find((s) => s.id === id);
										return (
											<Badge
												key={id}
												variant="destructive"
												className="text-[10px] cursor-pointer hover:bg-destructive/80"
												onClick={() => toggleShelfExclusion(id)}
											>
												{shelf?.name || `ID ${id}`}
												<X className="h-2.5 w-2.5 ml-1" />
											</Badge>
										);
									})}
								</div>
							)}
						</div>

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
			{getConnectorBenefits(EnumConnectorName.BOOKSTACK_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">
						What you get with BookStack integration:
					</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.BOOKSTACK_CONNECTOR)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
};
