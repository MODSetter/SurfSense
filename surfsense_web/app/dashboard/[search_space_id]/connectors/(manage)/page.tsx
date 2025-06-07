"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
	Edit,
	Plus,
	Trash2,
	RefreshCw,
	Calendar as CalendarIcon,
} from "lucide-react";

import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
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
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Label } from "@/components/ui/label";
import { getConnectorIcon } from "@/components/chat";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

// Helper function to format date with time
const formatDateTime = (dateString: string | null): string => {
	if (!dateString) return "Never";

	const date = new Date(dateString);
	return new Intl.DateTimeFormat("en-US", {
		year: "numeric",
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	}).format(date);
};

export default function ConnectorsPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;

	const { connectors, isLoading, error, deleteConnector, indexConnector } =
		useSearchSourceConnectors();
	const [connectorToDelete, setConnectorToDelete] = useState<number | null>(
		null,
	);
	const [indexingConnectorId, setIndexingConnectorId] = useState<number | null>(
		null,
	);
	const [datePickerOpen, setDatePickerOpen] = useState(false);
	const [selectedConnectorForIndexing, setSelectedConnectorForIndexing] = useState<number | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);

	useEffect(() => {
		if (error) {
			toast.error("Failed to load connectors");
			console.error("Error fetching connectors:", error);
		}
	}, [error]);

	// Handle connector deletion
	const handleDeleteConnector = async () => {
		if (connectorToDelete === null) return;

		try {
			await deleteConnector(connectorToDelete);
			toast.success("Connector deleted successfully");
		} catch (error) {
			console.error("Error deleting connector:", error);
			toast.error("Failed to delete connector");
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
			toast.success("Connector content indexed successfully");
		} catch (error) {
			console.error("Error indexing connector content:", error);
			toast.error(
				error instanceof Error
					? error.message
					: "Failed to index connector content",
			);
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
			toast.success("Connector content indexed successfully");
		} catch (error) {
			console.error("Error indexing connector content:", error);
			toast.error(
				error instanceof Error
					? error.message
					: "Failed to index connector content",
			);
		} finally {
			setIndexingConnectorId(null);
		}
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
					<h1 className="text-3xl font-bold tracking-tight">Connectors</h1>
					<p className="text-muted-foreground mt-2">
						Manage your connected services and data sources.
					</p>
				</div>
				<Button
					onClick={() =>
						router.push(`/dashboard/${searchSpaceId}/connectors/add`)
					}
				>
					<Plus className="mr-2 h-4 w-4" />
					Add Connector
				</Button>
			</motion.div>

			<Card>
				<CardHeader className="pb-3">
					<CardTitle>Your Connectors</CardTitle>
					<CardDescription>
						View and manage all your connected services.
					</CardDescription>
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
							<h3 className="text-lg font-medium mb-2">No connectors found</h3>
							<p className="text-muted-foreground mb-6">
								You haven't added any connectors yet. Add one to enhance your
								search capabilities.
							</p>
							<Button
								onClick={() =>
									router.push(`/dashboard/${searchSpaceId}/connectors/add`)
								}
							>
								<Plus className="mr-2 h-4 w-4" />
								Add Your First Connector
							</Button>
						</div>
					) : (
						<div className="rounded-md border">
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead>Name</TableHead>
										<TableHead>Type</TableHead>
										<TableHead>Last Indexed</TableHead>
										<TableHead className="text-right">Actions</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{connectors.map((connector) => (
										<TableRow key={connector.id}>
											<TableCell className="font-medium">
												{connector.name}
											</TableCell>
											<TableCell>
												{getConnectorIcon(connector.connector_type)}
											</TableCell>
											<TableCell>
												{connector.is_indexable
													? formatDateTime(connector.last_indexed_at)
													: "Not indexable"}
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
																			onClick={() =>
																				handleOpenDatePicker(connector.id)
																			}
																			disabled={
																				indexingConnectorId === connector.id
																			}
																		>
																			{indexingConnectorId === connector.id ? (
																				<RefreshCw className="h-4 w-4 animate-spin" />
																			) : (
																				<CalendarIcon className="h-4 w-4" />
																			)}
																			<span className="sr-only">
																				Index with Date Range
																			</span>
																		</Button>
																	</TooltipTrigger>
																	<TooltipContent>
																		<p>Index with Date Range</p>
																	</TooltipContent>
																</Tooltip>
															</TooltipProvider>
															<TooltipProvider>
																<Tooltip>
																	<TooltipTrigger asChild>
																		<Button
																			variant="outline"
																			size="sm"
																			onClick={() =>
																				handleQuickIndexConnector(connector.id)
																			}
																			disabled={
																				indexingConnectorId === connector.id
																			}
																		>
																			{indexingConnectorId === connector.id ? (
																				<RefreshCw className="h-4 w-4 animate-spin" />
																			) : (
																				<RefreshCw className="h-4 w-4" />
																			)}
																			<span className="sr-only">
																				Quick Index
																			</span>
																		</Button>
																	</TooltipTrigger>
																	<TooltipContent>
																		<p>Quick Index (Auto Date Range)</p>
																	</TooltipContent>
																</Tooltip>
															</TooltipProvider>
														</div>
													)}
													<Button
														variant="outline"
														size="sm"
														onClick={() =>
															router.push(
																`/dashboard/${searchSpaceId}/connectors/${connector.id}/edit`,
															)
														}
													>
														<Edit className="h-4 w-4" />
														<span className="sr-only">Edit</span>
													</Button>
													<AlertDialog>
														<AlertDialogTrigger asChild>
															<Button
																variant="outline"
																size="sm"
																className="text-destructive-foreground hover:bg-destructive/10"
																onClick={() =>
																	setConnectorToDelete(connector.id)
																}
															>
																<Trash2 className="h-4 w-4" />
																<span className="sr-only">Delete</span>
															</Button>
														</AlertDialogTrigger>
														<AlertDialogContent>
															<AlertDialogHeader>
																<AlertDialogTitle>
																	Delete Connector
																</AlertDialogTitle>
																<AlertDialogDescription>
																	Are you sure you want to delete this
																	connector? This action cannot be undone.
																</AlertDialogDescription>
															</AlertDialogHeader>
															<AlertDialogFooter>
																<AlertDialogCancel
																	onClick={() => setConnectorToDelete(null)}
																>
																	Cancel
																</AlertDialogCancel>
																<AlertDialogAction
																	className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
																	onClick={handleDeleteConnector}
																>
																	Delete
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
						<DialogTitle>Select Date Range for Indexing</DialogTitle>
						<DialogDescription>
							Choose the start and end dates for indexing content. Leave empty to use default range.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid grid-cols-2 gap-4">
							<div className="space-y-2">
								<Label htmlFor="start-date">Start Date</Label>
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
											{startDate ? format(startDate, "PPP") : "Pick a date"}
										</Button>
									</PopoverTrigger>
									<PopoverContent className="w-auto p-0" align="start">
										<Calendar
											mode="single"
											selected={startDate}
											onSelect={setStartDate}
											disabled={(date) =>
												date > new Date() || (endDate ? date > endDate : false)
											}
											initialFocus
										/>
									</PopoverContent>
								</Popover>
							</div>
							<div className="space-y-2">
								<Label htmlFor="end-date">End Date</Label>
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
											{endDate ? format(endDate, "PPP") : "Pick a date"}
										</Button>
									</PopoverTrigger>
									<PopoverContent className="w-auto p-0" align="start">
										<Calendar
											mode="single"
											selected={endDate}
											onSelect={setEndDate}
											disabled={(date) =>
												date > new Date() || (startDate ? date < startDate : false)
											}
											initialFocus
										/>
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
								Clear Dates
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => {
									const today = new Date();
									const thirtyDaysAgo = new Date(today);
									thirtyDaysAgo.setDate(today.getDate() - 30);
									setStartDate(thirtyDaysAgo);
									setEndDate(today);
								}}
							>
								Last 30 Days
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => {
									const today = new Date();
									const yearAgo = new Date(today);
									yearAgo.setFullYear(today.getFullYear() - 1);
									setStartDate(yearAgo);
									setEndDate(today);
								}}
							>
								Last Year
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
							Cancel
						</Button>
						<Button onClick={handleIndexConnector}>
							Start Indexing
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
