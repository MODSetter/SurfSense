"use client";

import { format } from "date-fns";
import {
	Calendar as CalendarIcon,
	Clock,
	Edit,
	Loader2,
	Plus,
	RefreshCw,
	Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";
import { cn } from "@/lib/utils";

export default function ConnectorsPage() {
	const t = useTranslations("connectors");
	const tCommon = useTranslations("common");

	// Helper function to format date with time
	const formatDateTime = (dateString: string | null): string => {
		if (!dateString) return t("never");

		const date = new Date(dateString);
		return new Intl.DateTimeFormat("en-US", {
			year: "numeric",
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		}).format(date);
	};
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const today = new Date();

	const { connectors, isLoading, error, deleteConnector, indexConnector, updateConnector } =
		useSearchSourceConnectors(false, parseInt(searchSpaceId));
	const [connectorToDelete, setConnectorToDelete] = useState<number | null>(null);
	const [indexingConnectorId, setIndexingConnectorId] = useState<number | null>(null);
	const [datePickerOpen, setDatePickerOpen] = useState(false);
	const [selectedConnectorForIndexing, setSelectedConnectorForIndexing] = useState<number | null>(
		null
	);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);

	// Periodic indexing state
	const [periodicDialogOpen, setPeriodicDialogOpen] = useState(false);
	const [selectedConnectorForPeriodic, setSelectedConnectorForPeriodic] = useState<number | null>(
		null
	);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState<string>("1440");
	const [customFrequency, setCustomFrequency] = useState<string>("");
	const [isSavingPeriodic, setIsSavingPeriodic] = useState(false);

	useEffect(() => {
		if (error) {
			toast.error(t("failed_load"));
			console.error("Error fetching connectors:", error);
		}
	}, [error, t]);

	// Handle connector deletion
	const handleDeleteConnector = async () => {
		if (connectorToDelete === null) return;

		try {
			await deleteConnector(connectorToDelete);
			toast.success(t("delete_success"));
		} catch (error) {
			console.error("Error deleting connector:", error);
			toast.error(t("delete_failed"));
		} finally {
			setConnectorToDelete(null);
		}
	};

	// Handle opening date picker for indexing
	const handleOpenDatePicker = (connectorId: number) => {
		setSelectedConnectorForIndexing(connectorId);
		setDatePickerOpen(true);
	};

	// Handle connector indexing with dates
	const handleIndexConnector = async () => {
		if (selectedConnectorForIndexing === null) return;

		setDatePickerOpen(false);

		try {
			setIndexingConnectorId(selectedConnectorForIndexing);
			const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
			const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

			await indexConnector(selectedConnectorForIndexing, searchSpaceId, startDateStr, endDateStr);
			toast.success(t("indexing_started"));
		} catch (error) {
			console.error("Error indexing connector content:", error);
			toast.error(error instanceof Error ? error.message : t("indexing_failed"));
		} finally {
			setIndexingConnectorId(null);
			setSelectedConnectorForIndexing(null);
			setStartDate(undefined);
			setEndDate(undefined);
		}
	};

	// Handle indexing without date picker (for quick indexing)
	const handleQuickIndexConnector = async (connectorId: number) => {
		setIndexingConnectorId(connectorId);
		try {
			await indexConnector(connectorId, searchSpaceId);
			toast.success(t("indexing_started"));
		} catch (error) {
			console.error("Error indexing connector content:", error);
			toast.error(error instanceof Error ? error.message : t("indexing_failed"));
		} finally {
			setIndexingConnectorId(null);
		}
	};

	// Handle opening periodic indexing dialog
	const handleOpenPeriodicDialog = (connectorId: number) => {
		const connector = connectors.find((c) => c.id === connectorId);
		if (!connector) return;

		setSelectedConnectorForPeriodic(connectorId);
		setPeriodicEnabled(connector.periodic_indexing_enabled);

		if (connector.indexing_frequency_minutes) {
			// Check if it's a preset value
			const presetValues = ["15", "60", "360", "720", "1440", "10080"];
			if (presetValues.includes(connector.indexing_frequency_minutes.toString())) {
				setFrequencyMinutes(connector.indexing_frequency_minutes.toString());
				setCustomFrequency("");
			} else {
				setFrequencyMinutes("custom");
				setCustomFrequency(connector.indexing_frequency_minutes.toString());
			}
		} else {
			setFrequencyMinutes("1440");
			setCustomFrequency("");
		}

		setPeriodicDialogOpen(true);
	};

	// Handle saving periodic indexing configuration
	const handleSavePeriodicIndexing = async () => {
		if (selectedConnectorForPeriodic === null) return;

		const connector = connectors.find((c) => c.id === selectedConnectorForPeriodic);
		if (!connector) return;

		setIsSavingPeriodic(true);
		try {
			// Determine the frequency value
			let frequency: number | null = null;
			if (periodicEnabled) {
				if (frequencyMinutes === "custom") {
					frequency = parseInt(customFrequency, 10);
					if (isNaN(frequency) || frequency <= 0) {
						toast.error("Please enter a valid frequency in minutes");
						setIsSavingPeriodic(false);
						return;
					}
				} else {
					frequency = parseInt(frequencyMinutes, 10);
				}
			}

			await updateConnector(selectedConnectorForPeriodic, {
				periodic_indexing_enabled: periodicEnabled,
				indexing_frequency_minutes: frequency,
			});

			toast.success(
				periodicEnabled
					? "Periodic indexing enabled successfully"
					: "Periodic indexing disabled successfully"
			);
			setPeriodicDialogOpen(false);
		} catch (error) {
			console.error("Error updating periodic indexing:", error);
			toast.error(error instanceof Error ? error.message : "Failed to update periodic indexing");
		} finally {
			setIsSavingPeriodic(false);
			setSelectedConnectorForPeriodic(null);
		}
	};

	// Format frequency for display
	const formatFrequency = (minutes: number): string => {
		if (minutes < 60) return `${minutes}m`;
		if (minutes < 1440) return `${Math.floor(minutes / 60)}h`;
		if (minutes < 10080) return `${Math.floor(minutes / 1440)}d`;
		return `${Math.floor(minutes / 10080)}w`;
	};

	return (
		<div className="container mx-auto py-8 max-w-6xl">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="mb-8 flex items-center justify-between"
			>
				<div>
					<h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
					<p className="text-muted-foreground mt-2">{t("subtitle")}</p>
				</div>
				<Button onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}>
					<Plus className="mr-2 h-4 w-4" />
					{t("add_connector")}
				</Button>
			</motion.div>

			<Card>
				<CardHeader className="pb-3">
					<CardTitle>{t("your_connectors")}</CardTitle>
					<CardDescription>{t("view_manage")}</CardDescription>
				</CardHeader>
				<CardContent>
					{isLoading ? (
						<div className="flex justify-center py-8">
							<div className="animate-pulse text-center">
								<div className="h-6 w-32 bg-muted rounded mx-auto mb-2"></div>
								<div className="h-4 w-48 bg-muted rounded mx-auto"></div>
							</div>
						</div>
					) : connectors.length === 0 ? (
						<div className="text-center py-12">
							<h3 className="text-lg font-medium mb-2">{t("no_connectors")}</h3>
							<p className="text-muted-foreground mb-6">{t("no_connectors_desc")}</p>
							<Button onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}>
								<Plus className="mr-2 h-4 w-4" />
								{t("add_first")}
							</Button>
						</div>
					) : (
						<div className="rounded-md border">
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead>{t("name")}</TableHead>
										<TableHead>{t("type")}</TableHead>
										<TableHead>{t("last_indexed")}</TableHead>
										<TableHead>{t("periodic")}</TableHead>
										<TableHead className="text-right">{t("actions")}</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{connectors.map((connector) => (
										<TableRow key={connector.id}>
											<TableCell className="font-medium">{connector.name}</TableCell>
											<TableCell>{getConnectorIcon(connector.connector_type)}</TableCell>
											<TableCell>
												{connector.is_indexable
													? formatDateTime(connector.last_indexed_at)
													: t("not_indexable")}
											</TableCell>
											<TableCell>
												{connector.is_indexable ? (
													connector.periodic_indexing_enabled ? (
														<TooltipProvider>
															<Tooltip>
																<TooltipTrigger asChild>
																	<div className="flex items-center gap-1 text-green-600 dark:text-green-400">
																		<Clock className="h-4 w-4" />
																		<span className="text-sm font-medium">
																			{connector.indexing_frequency_minutes
																				? formatFrequency(connector.indexing_frequency_minutes)
																				: "Enabled"}
																		</span>
																	</div>
																</TooltipTrigger>
																<TooltipContent>
																	<p>
																		Runs every {connector.indexing_frequency_minutes} minutes
																		{connector.next_scheduled_at && (
																			<>
																				<br />
																				Next: {formatDateTime(connector.next_scheduled_at)}
																			</>
																		)}
																	</p>
																</TooltipContent>
															</Tooltip>
														</TooltipProvider>
													) : (
														<span className="text-sm text-muted-foreground">Disabled</span>
													)
												) : (
													<span className="text-sm text-muted-foreground">-</span>
												)}
											</TableCell>
											<TableCell className="text-right">
												<div className="flex justify-end gap-2">
													{connector.is_indexable && (
														<div className="flex gap-1">
															<TooltipProvider>
																<Tooltip>
																	<TooltipTrigger asChild>
																		<Button
																			variant="outline"
																			size="sm"
																			onClick={() => handleOpenDatePicker(connector.id)}
																			disabled={indexingConnectorId === connector.id}
																		>
																			{indexingConnectorId === connector.id ? (
																				<RefreshCw className="h-4 w-4 animate-spin" />
																			) : (
																				<CalendarIcon className="h-4 w-4" />
																			)}
																			<span className="sr-only">{t("index_date_range")}</span>
																		</Button>
																	</TooltipTrigger>
																	<TooltipContent>
																		<p>{t("index_date_range")}</p>
																	</TooltipContent>
																</Tooltip>
															</TooltipProvider>
															<TooltipProvider>
																<Tooltip>
																	<TooltipTrigger asChild>
																		<Button
																			variant="outline"
																			size="sm"
																			onClick={() => handleQuickIndexConnector(connector.id)}
																			disabled={indexingConnectorId === connector.id}
																		>
																			{indexingConnectorId === connector.id ? (
																				<RefreshCw className="h-4 w-4 animate-spin" />
																			) : (
																				<RefreshCw className="h-4 w-4" />
																			)}
																			<span className="sr-only">{t("quick_index")}</span>
																		</Button>
																	</TooltipTrigger>
																	<TooltipContent>
																		<p>{t("quick_index_auto")}</p>
																	</TooltipContent>
																</Tooltip>
															</TooltipProvider>
														</div>
													)}
													{connector.is_indexable && (
														<TooltipProvider>
															<Tooltip>
																<TooltipTrigger asChild>
																	<Button
																		variant="outline"
																		size="sm"
																		onClick={() => handleOpenPeriodicDialog(connector.id)}
																	>
																		<Clock className="h-4 w-4" />
																		<span className="sr-only">Configure Periodic Indexing</span>
																	</Button>
																</TooltipTrigger>
																<TooltipContent>
																	<p>Configure Periodic Indexing</p>
																</TooltipContent>
															</Tooltip>
														</TooltipProvider>
													)}
													<Button
														variant="outline"
														size="sm"
														onClick={() =>
															router.push(
																`/dashboard/${searchSpaceId}/connectors/${connector.id}/edit`
															)
														}
													>
														<Edit className="h-4 w-4" />
														<span className="sr-only">{tCommon("edit")}</span>
													</Button>
													<AlertDialog>
														<AlertDialogTrigger asChild>
															<Button
																variant="outline"
																size="sm"
																className="text-destructive-foreground hover:bg-destructive/10"
																onClick={() => setConnectorToDelete(connector.id)}
															>
																<Trash2 className="h-4 w-4" />
																<span className="sr-only">{tCommon("delete")}</span>
															</Button>
														</AlertDialogTrigger>
														<AlertDialogContent>
															<AlertDialogHeader>
																<AlertDialogTitle>{t("delete_connector")}</AlertDialogTitle>
																<AlertDialogDescription>
																	{t("delete_confirm")}
																</AlertDialogDescription>
															</AlertDialogHeader>
															<AlertDialogFooter>
																<AlertDialogCancel onClick={() => setConnectorToDelete(null)}>
																	{tCommon("cancel")}
																</AlertDialogCancel>
																<AlertDialogAction
																	className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
																	onClick={handleDeleteConnector}
																>
																	{tCommon("delete")}
																</AlertDialogAction>
															</AlertDialogFooter>
														</AlertDialogContent>
													</AlertDialog>
												</div>
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					)}
				</CardContent>
			</Card>

			{/* Date Picker Dialog */}
			<Dialog open={datePickerOpen} onOpenChange={setDatePickerOpen}>
				<DialogContent className="sm:max-w-[500px]">
					<DialogHeader>
						<DialogTitle>{t("select_date_range")}</DialogTitle>
						<DialogDescription>{t("select_date_range_desc")}</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid grid-cols-2 gap-4">
							<div className="space-y-2">
								<Label htmlFor="start-date">{t("start_date")}</Label>
								<Popover>
									<PopoverTrigger asChild>
										<Button
											id="start-date"
											variant="outline"
											className={cn(
												"w-full justify-start text-left font-normal",
												!startDate && "text-muted-foreground"
											)}
										>
											<CalendarIcon className="mr-2 h-4 w-4" />
											{startDate ? format(startDate, "PPP") : t("pick_date")}
										</Button>
									</PopoverTrigger>
									<PopoverContent className="w-auto p-0" align="start">
										<Calendar
											mode="single"
											selected={startDate}
											onSelect={setStartDate}
											initialFocus
										/>
									</PopoverContent>
								</Popover>
							</div>
							<div className="space-y-2">
								<Label htmlFor="end-date">{t("end_date")}</Label>
								<Popover>
									<PopoverTrigger asChild>
										<Button
											id="end-date"
											variant="outline"
											className={cn(
												"w-full justify-start text-left font-normal",
												!endDate && "text-muted-foreground"
											)}
										>
											<CalendarIcon className="mr-2 h-4 w-4" />
											{endDate ? format(endDate, "PPP") : t("pick_date")}
										</Button>
									</PopoverTrigger>
									<PopoverContent className="w-auto p-0" align="start">
										<Calendar mode="single" selected={endDate} onSelect={setEndDate} initialFocus />
									</PopoverContent>
								</Popover>
							</div>
						</div>
						<div className="flex gap-2">
							<Button
								variant="outline"
								size="sm"
								onClick={() => {
									setStartDate(undefined);
									setEndDate(undefined);
								}}
							>
								{t("clear_dates")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => {
									const thirtyDaysAgo = new Date(today);
									thirtyDaysAgo.setDate(today.getDate() - 30);
									setStartDate(thirtyDaysAgo);
									setEndDate(today);
								}}
							>
								{t("last_30_days")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => {
									const yearAgo = new Date(today);
									yearAgo.setFullYear(today.getFullYear() - 1);
									setStartDate(yearAgo);
									setEndDate(today);
								}}
							>
								{t("last_year")}
							</Button>
						</div>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => {
								setDatePickerOpen(false);
								setSelectedConnectorForIndexing(null);
								setStartDate(undefined);
								setEndDate(undefined);
							}}
						>
							{tCommon("cancel")}
						</Button>
						<Button onClick={handleIndexConnector}>{t("start_indexing")}</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Periodic Indexing Configuration Dialog */}
			<Dialog open={periodicDialogOpen} onOpenChange={setPeriodicDialogOpen}>
				<DialogContent className="sm:max-w-[500px]">
					<DialogHeader>
						<DialogTitle>Configure Periodic Indexing</DialogTitle>
						<DialogDescription>
							Set up automatic indexing at regular intervals for this connector.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-6 py-4">
						<div className="flex items-center justify-between space-x-2">
							<div className="space-y-0.5">
								<Label htmlFor="periodic-enabled" className="text-base">
									Enable Periodic Indexing
								</Label>
								<p className="text-sm text-muted-foreground">
									Automatically index this connector at regular intervals
								</p>
							</div>
							<Switch
								id="periodic-enabled"
								checked={periodicEnabled}
								onCheckedChange={setPeriodicEnabled}
							/>
						</div>

						{periodicEnabled && (
							<div className="space-y-4">
								<div className="space-y-2">
									<Label htmlFor="frequency">Indexing Frequency</Label>
									<Select value={frequencyMinutes} onValueChange={setFrequencyMinutes}>
										<SelectTrigger id="frequency">
											<SelectValue placeholder="Select frequency" />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="15">Every 15 minutes</SelectItem>
											<SelectItem value="60">Every hour</SelectItem>
											<SelectItem value="360">Every 6 hours</SelectItem>
											<SelectItem value="720">Every 12 hours</SelectItem>
											<SelectItem value="1440">Daily (24 hours)</SelectItem>
											<SelectItem value="10080">Weekly (7 days)</SelectItem>
											<SelectItem value="custom">Custom</SelectItem>
										</SelectContent>
									</Select>
								</div>

								{frequencyMinutes === "custom" && (
									<div className="space-y-2">
										<Label htmlFor="custom-frequency">Custom Frequency (minutes)</Label>
										<Input
											id="custom-frequency"
											type="number"
											min="1"
											placeholder="Enter minutes"
											value={customFrequency}
											onChange={(e) => setCustomFrequency(e.target.value)}
										/>
										<p className="text-xs text-muted-foreground">
											Enter the number of minutes between each indexing run
										</p>
									</div>
								)}

								<div className="rounded-lg bg-muted p-3 text-sm">
									<p className="font-medium mb-1">Preview:</p>
									<p className="text-muted-foreground">
										{frequencyMinutes === "custom" && customFrequency
											? `Will run every ${customFrequency} minutes`
											: frequencyMinutes === "15"
												? "Will run every 15 minutes"
												: frequencyMinutes === "60"
													? "Will run every hour"
													: frequencyMinutes === "360"
														? "Will run every 6 hours"
														: frequencyMinutes === "720"
															? "Will run every 12 hours"
															: frequencyMinutes === "1440"
																? "Will run daily (every 24 hours)"
																: frequencyMinutes === "10080"
																	? "Will run weekly (every 7 days)"
																	: "Select a frequency above"}
									</p>
								</div>
							</div>
						)}
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => {
								setPeriodicDialogOpen(false);
								setSelectedConnectorForPeriodic(null);
							}}
						>
							Cancel
						</Button>
						<Button onClick={handleSavePeriodicIndexing} disabled={isSavingPeriodic}>
							{isSavingPeriodic && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
							Save Configuration
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
