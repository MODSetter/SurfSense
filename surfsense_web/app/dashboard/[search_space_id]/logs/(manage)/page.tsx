"use client";

import {
	type ColumnDef,
	type ColumnFiltersState,
	flexRender,
	getCoreRowModel,
	getFacetedUniqueValues,
	getFilteredRowModel,
	getPaginationRowModel,
	getSortedRowModel,
	type PaginationState,
	type Row,
	type SortingState,
	useReactTable,
	type VisibilityState,
} from "@tanstack/react-table";
import {
	Activity,
	AlertCircle,
	AlertTriangle,
	Bug,
	CheckCircle2,
	ChevronDown,
	ChevronFirst,
	ChevronLast,
	ChevronLeft,
	ChevronRight,
	ChevronUp,
	CircleAlert,
	CircleX,
	Clock,
	Columns3,
	Filter,
	Info,
	ListFilter,
	MoreHorizontal,
	RefreshCw,
	Terminal,
	Trash,
	X,
	Zap,
} from "lucide-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import React, { useContext, useId, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { JsonMetadataViewer } from "@/components/json-metadata-viewer";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pagination, PaginationContent, PaginationItem } from "@/components/ui/pagination";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { type Log, type LogLevel, type LogStatus, useLogs, useLogsSummary } from "@/hooks/use-logs";
import { cn } from "@/lib/utils";

// Define animation variants for reuse
const fadeInScale: Variants = {
	hidden: { opacity: 0, scale: 0.95 },
	visible: {
		opacity: 1,
		scale: 1,
		transition: { type: "spring", stiffness: 300, damping: 30 },
	},
	exit: {
		opacity: 0,
		scale: 0.95,
		transition: { duration: 0.15 },
	},
};

// Log level icons and colors
const logLevelConfig = {
	DEBUG: { icon: Bug, color: "text-muted-foreground", bgColor: "bg-muted/50" },
	INFO: { icon: Info, color: "text-blue-600", bgColor: "bg-blue-50" },
	WARNING: { icon: AlertTriangle, color: "text-yellow-600", bgColor: "bg-yellow-50" },
	ERROR: { icon: AlertCircle, color: "text-red-600", bgColor: "bg-red-50" },
	CRITICAL: { icon: Zap, color: "text-purple-600", bgColor: "bg-purple-50" },
} as const;

// Log status icons and colors
const logStatusConfig = {
	IN_PROGRESS: { icon: Clock, color: "text-blue-600", bgColor: "bg-blue-50" },
	SUCCESS: { icon: CheckCircle2, color: "text-green-600", bgColor: "bg-green-50" },
	FAILED: { icon: X, color: "text-red-600", bgColor: "bg-red-50" },
} as const;

function MessageDetails({
	message,
	taskName,
	metadata,
	createdAt,
	children,
}: {
	message: string;
	taskName?: string;
	metadata?: any;
	createdAt?: string;
	children: React.ReactNode;
}) {
	return (
		<AlertDialog>
			<AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
			<AlertDialogContent className="max-w-3xl w-full">
				<div className="flex items-start justify-between gap-4">
					<div>
						<AlertDialogTitle className="text-lg">Log details</AlertDialogTitle>
						{createdAt && (
							<p className="text-xs text-muted-foreground mt-1">
								{new Date(createdAt).toLocaleString()}
							</p>
						)}
					</div>
					<div className="shrink-0">
						<AlertDialogCancel className="text-sm">Close</AlertDialogCancel>
					</div>
				</div>

				<div className="mt-4 space-y-4">
					{taskName && (
						<div className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-1 rounded inline-block">
							{taskName}
						</div>
					)}

					<div className="bg-muted p-3 rounded max-h-[40vh] overflow-auto text-sm whitespace-pre-wrap">
						{message}
					</div>
				</div>

				<AlertDialogFooter />
			</AlertDialogContent>
		</AlertDialog>
	);
}

const createColumns = (t: (key: string) => string): ColumnDef<Log>[] => [
	{
		id: "select",
		header: ({ table }) => (
			<Checkbox
				checked={
					table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")
				}
				onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
				aria-label="Select all"
			/>
		),
		cell: ({ row }) => (
			<Checkbox
				checked={row.getIsSelected()}
				onCheckedChange={(value) => row.toggleSelected(!!value)}
				aria-label="Select row"
			/>
		),
		size: 28,
		enableSorting: false,
		enableHiding: false,
	},
	{
		header: t("level"),
		accessorKey: "level",
		cell: ({ row }) => {
			const level = row.getValue("level") as LogLevel;
			const config = logLevelConfig[level];
			const Icon = config.icon;
			return (
				<motion.div
					className="flex items-center gap-2"
					whileHover={{ scale: 1.05 }}
					transition={{ type: "spring", stiffness: 300 }}
				>
					<div
						className={cn("flex h-7 w-7 items-center justify-center rounded-full", config.bgColor)}
					>
						<Icon size={16} className={config.color} />
					</div>
					<span className={cn("font-medium text-xs", config.color)}>{level}</span>
				</motion.div>
			);
		},
		size: 120,
	},
	{
		header: t("status"),
		accessorKey: "status",
		cell: ({ row }) => {
			const status = row.getValue("status") as LogStatus;
			const config = logStatusConfig[status];
			const Icon = config.icon;
			return (
				<motion.div
					className="flex items-center gap-2"
					whileHover={{ scale: 1.05 }}
					transition={{ type: "spring", stiffness: 300 }}
				>
					<div
						className={cn("flex h-6 w-6 items-center justify-center rounded-full", config.bgColor)}
					>
						<Icon size={14} className={config.color} />
					</div>
					<span className={cn("font-medium text-xs", config.color)}>
						{status.replace("_", " ")}
					</span>
				</motion.div>
			);
		},
		size: 140,
	},
	{
		header: t("source"),
		accessorKey: "source",
		cell: ({ row }) => {
			const source = row.getValue("source") as string;
			return (
				<motion.div
					className="flex items-center gap-2"
					whileHover={{ scale: 1.02 }}
					transition={{ type: "spring", stiffness: 300 }}
				>
					<Terminal size={14} className="text-muted-foreground" />
					<span className="text-sm font-mono">{source || t("system")}</span>
				</motion.div>
			);
		},
		size: 150,
	},
	{
		header: t("message"),
		accessorKey: "message",
		cell: ({ row }) => {
			const message = row.getValue("message") as string;
			const taskName = row.original.log_metadata?.task_name;
			const createdAt = row.getValue("created_at") as string;

			return (
				<MessageDetails
					message={message}
					taskName={taskName}
					metadata={row.original.log_metadata}
					createdAt={createdAt}
				>
					<div className="flex flex-col gap-1 max-w-[400px] cursor-pointer">
						{taskName && (
							<div
								className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-1 rounded truncate"
								title={taskName}
							>
								{taskName}
							</div>
						)}
						<div className="text-sm truncate" title={message}>
							{message.length > 100 ? `${message.substring(0, 100)}...` : message}
						</div>
					</div>
				</MessageDetails>
			);
		},
		size: 400,
	},
	{
		header: t("created_at"),
		accessorKey: "created_at",
		cell: ({ row }) => {
			const date = new Date(row.getValue("created_at"));
			return (
				<div className="flex flex-col gap-1 text-xs">
					<div>{date.toLocaleDateString()}</div>
					<div className="text-muted-foreground">{date.toLocaleTimeString()}</div>
				</div>
			);
		},
		size: 120,
	},
	{
		id: "actions",
		header: () => <span className="sr-only">{t("actions")}</span>,
		cell: ({ row }) => <LogRowActions row={row} t={t} />,
		size: 60,
		enableHiding: false,
	},
];

// Default columns for backward compatibility
const columns: ColumnDef<Log>[] = createColumns((key) => key);

// Create a context to share functions
const LogsContext = React.createContext<{
	deleteLog: (id: number) => Promise<boolean>;
	refreshLogs: () => Promise<void>;
} | null>(null);

export default function LogsManagePage() {
	const t = useTranslations("logs");
	const id = useId();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const {
		logs,
		loading: logsLoading,
		error: logsError,
		refreshLogs,
		deleteLog,
	} = useLogs(searchSpaceId);
	const {
		summary,
		loading: summaryLoading,
		error: summaryError,
		refreshSummary,
	} = useLogsSummary(searchSpaceId, 24);

	const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
	const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 20,
	});
	const [sorting, setSorting] = useState<SortingState>([
		{
			id: "created_at",
			desc: true,
		},
	]);

	const inputRef = useRef<HTMLInputElement>(null);

	// Create translated columns
	const translatedColumns = useMemo(() => createColumns(t), [t]);

	const table = useReactTable({
		data: logs,
		columns: translatedColumns,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		onSortingChange: setSorting,
		enableSortingRemoval: false,
		getPaginationRowModel: getPaginationRowModel(),
		onPaginationChange: setPagination,
		onColumnFiltersChange: setColumnFilters,
		onColumnVisibilityChange: setColumnVisibility,
		getFilteredRowModel: getFilteredRowModel(),
		getFacetedUniqueValues: getFacetedUniqueValues(),
		state: {
			sorting,
			pagination,
			columnFilters,
			columnVisibility,
		},
	});

	// Get unique values for filters
	const uniqueLevels = useMemo(() => {
		const levelColumn = table.getColumn("level");
		if (!levelColumn) return [];
		return Array.from(levelColumn.getFacetedUniqueValues().keys()).sort();
	}, [table.getColumn]);

	const uniqueStatuses = useMemo(() => {
		const statusColumn = table.getColumn("status");
		if (!statusColumn) return [];
		return Array.from(statusColumn.getFacetedUniqueValues().keys()).sort();
	}, [table.getColumn]);

	const handleDeleteRows = async () => {
		const selectedRows = table.getSelectedRowModel().rows;

		if (selectedRows.length === 0) {
			toast.error("No rows selected");
			return;
		}

		const deletePromises = selectedRows.map((row) => deleteLog(row.original.id));

		try {
			const results = await Promise.all(deletePromises);
			const allSuccessful = results.every((result) => result === true);

			if (allSuccessful) {
				toast.success(`Successfully deleted ${selectedRows.length} log(s)`);
			} else {
				toast.error("Some logs could not be deleted");
			}

			await refreshLogs();
			table.resetRowSelection();
		} catch (error: any) {
			console.error("Error deleting logs:", error);
			toast.error("Error deleting logs");
		}
	};

	const handleRefresh = async () => {
		await Promise.all([refreshLogs(), refreshSummary()]);
		toast.success("Logs refreshed");
	};

	return (
		<LogsContext.Provider
			value={{
				deleteLog: deleteLog || (() => Promise.resolve(false)),
				refreshLogs: refreshLogs || (() => Promise.resolve()),
			}}
		>
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.3 }}
				className="w-full px-6 py-4 space-y-6"
			>
				{/* Summary Dashboard */}
				<LogsSummaryDashboard
					summary={summary}
					loading={summaryLoading}
					error={summaryError}
					onRefresh={refreshSummary}
				/>

				{/* Logs Table Header */}
				<motion.div
					className="flex items-center justify-between"
					initial={{ opacity: 0, y: 10 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.1 }}
				>
					<div>
						<h2 className="text-2xl font-bold tracking-tight">{t("title")}</h2>
						<p className="text-muted-foreground">{t("subtitle")}</p>
					</div>
					<Button onClick={handleRefresh} variant="outline" size="sm">
						<RefreshCw className="w-4 h-4 mr-2" />
						{t("refresh")}
					</Button>
				</motion.div>

				{/* Filters */}
				<LogsFilters
					table={table}
					uniqueLevels={uniqueLevels}
					uniqueStatuses={uniqueStatuses}
					inputRef={inputRef}
					id={id}
				/>

				{/* Delete Button */}
				{table.getSelectedRowModel().rows.length > 0 && (
					<motion.div
						initial={{ opacity: 0, y: -10 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -10 }}
						className="flex justify-end"
					>
						<AlertDialog>
							<AlertDialogTrigger asChild>
								<Button variant="outline">
									<Trash className="-ms-1 me-2 opacity-60" size={16} strokeWidth={2} />
									{t("delete_selected")}
									<span className="-me-1 ms-3 inline-flex h-5 max-h-full items-center rounded border border-border bg-background px-1 font-[inherit] text-[0.625rem] font-medium text-muted-foreground/70">
										{table.getSelectedRowModel().rows.length}
									</span>
								</Button>
							</AlertDialogTrigger>
							<AlertDialogContent>
								<div className="flex flex-col gap-2 max-sm:items-center sm:flex-row sm:gap-4">
									<div className="flex size-9 shrink-0 items-center justify-center rounded-full border border-border">
										<CircleAlert className="opacity-80" size={16} strokeWidth={2} />
									</div>
									<AlertDialogHeader>
										<AlertDialogTitle>{t("confirm_title")}</AlertDialogTitle>
										<AlertDialogDescription>
											{t("confirm_delete_desc", { count: table.getSelectedRowModel().rows.length })}
										</AlertDialogDescription>
									</AlertDialogHeader>
								</div>
								<AlertDialogFooter>
									<AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
									<AlertDialogAction onClick={handleDeleteRows}>{t("delete")}</AlertDialogAction>
								</AlertDialogFooter>
							</AlertDialogContent>
						</AlertDialog>
					</motion.div>
				)}

				{/* Logs Table */}
				<LogsTable
					table={table}
					logs={logs}
					loading={logsLoading}
					error={logsError}
					onRefresh={refreshLogs}
					id={id}
					t={t}
				/>
			</motion.div>
		</LogsContext.Provider>
	);
}

// Summary Dashboard Component
function LogsSummaryDashboard({
	summary,
	loading,
	error,
	onRefresh,
}: {
	summary: any;
	loading: boolean;
	error: string | null;
	onRefresh: () => void;
}) {
	const t = useTranslations("logs");
	if (loading) {
		return (
			<motion.div
				className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
			>
				{[...Array(4)].map((_, i) => (
					<Card key={i}>
						<CardHeader className="pb-2">
							<div className="h-4 bg-muted rounded animate-pulse" />
						</CardHeader>
						<CardContent>
							<div className="h-8 bg-muted rounded animate-pulse" />
						</CardContent>
					</Card>
				))}
			</motion.div>
		);
	}

	if (error || !summary) {
		return (
			<Card>
				<CardContent className="flex items-center justify-center h-32">
					<div className="flex flex-col items-center gap-2">
						<AlertCircle className="h-8 w-8 text-destructive" />
						<p className="text-sm text-destructive">{t("failed_load_summary")}</p>
						<Button variant="outline" size="sm" onClick={onRefresh}>
							{t("retry")}
						</Button>
					</div>
				</CardContent>
			</Card>
		);
	}

	return (
		<motion.div
			className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ staggerChildren: 0.1 }}
		>
			{/* Total Logs */}
			<motion.div variants={fadeInScale}>
				<Card>
					<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
						<CardTitle className="text-sm font-medium">{t("total_logs")}</CardTitle>
						<Activity className="h-4 w-4 text-muted-foreground" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold">{summary.total_logs}</div>
						<p className="text-xs text-muted-foreground">
							{t("last_hours", { hours: summary.time_window_hours })}
						</p>
					</CardContent>
				</Card>
			</motion.div>

			{/* Active Tasks */}
			<motion.div variants={fadeInScale}>
				<Card>
					<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
						<CardTitle className="text-sm font-medium">{t("active_tasks")}</CardTitle>
						<Clock className="h-4 w-4 text-blue-600" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-blue-600">
							{summary.active_tasks?.length || 0}
						</div>
						<p className="text-xs text-muted-foreground">{t("currently_running")}</p>
					</CardContent>
				</Card>
			</motion.div>

			{/* Success Rate */}
			<motion.div variants={fadeInScale}>
				<Card>
					<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
						<CardTitle className="text-sm font-medium">{t("success_rate")}</CardTitle>
						<CheckCircle2 className="h-4 w-4 text-green-600" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-green-600">
							{summary.total_logs > 0
								? Math.round(((summary.by_status?.SUCCESS || 0) / summary.total_logs) * 100)
								: 0}
							%
						</div>
						<p className="text-xs text-muted-foreground">
							{summary.by_status?.SUCCESS || 0} {t("successful")}
						</p>
					</CardContent>
				</Card>
			</motion.div>

			{/* Recent Failures */}
			<motion.div variants={fadeInScale}>
				<Card>
					<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
						<CardTitle className="text-sm font-medium">{t("recent_failures")}</CardTitle>
						<AlertCircle className="h-4 w-4 text-red-600" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-red-600">
							{summary.recent_failures?.length || 0}
						</div>
						<p className="text-xs text-muted-foreground">{t("need_attention")}</p>
					</CardContent>
				</Card>
			</motion.div>
		</motion.div>
	);
}

// Filters Component
function LogsFilters({
	table,
	uniqueLevels,
	uniqueStatuses,
	inputRef,
	id,
}: {
	table: any;
	uniqueLevels: string[];
	uniqueStatuses: string[];
	inputRef: React.RefObject<HTMLInputElement | null>;
	id: string;
}) {
	const t = useTranslations("logs");
	return (
		<motion.div
			className="flex flex-wrap items-center justify-between gap-3"
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ delay: 0.2 }}
		>
			<div className="flex items-center gap-3">
				{/* Search Input */}
				<motion.div className="relative" variants={fadeInScale}>
					<Input
						ref={inputRef}
						className={cn(
							"peer min-w-60 ps-9",
							Boolean(table.getColumn("message")?.getFilterValue()) && "pe-9"
						)}
						value={(table.getColumn("message")?.getFilterValue() ?? "") as string}
						onChange={(e) => table.getColumn("message")?.setFilterValue(e.target.value)}
						placeholder={t("filter_by_message")}
						type="text"
					/>
					<div className="pointer-events-none absolute inset-y-0 start-0 flex items-center justify-center ps-3 text-muted-foreground/80">
						<ListFilter size={16} strokeWidth={2} />
					</div>
					{Boolean(table.getColumn("message")?.getFilterValue()) && (
						<Button
							className="absolute inset-y-0 end-0 flex h-full w-9 items-center justify-center rounded-e-lg text-muted-foreground/80 hover:text-foreground"
							variant="ghost"
							size="icon"
							onClick={() => {
								table.getColumn("message")?.setFilterValue("");
								inputRef.current?.focus();
							}}
						>
							<CircleX size={16} strokeWidth={2} />
						</Button>
					)}
				</motion.div>

				{/* Level Filter */}
				<FilterDropdown
					title={t("level")}
					column={table.getColumn("level")}
					options={uniqueLevels}
					id={`${id}-level`}
					t={t}
				/>

				{/* Status Filter */}
				<FilterDropdown
					title={t("status")}
					column={table.getColumn("status")}
					options={uniqueStatuses}
					id={`${id}-status`}
					t={t}
				/>

				{/* Column Visibility */}
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="outline">
							<Columns3 className="-ms-1 me-2 opacity-60" size={16} strokeWidth={2} />
							{t("view")}
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
						<DropdownMenuLabel>{t("toggle_columns")}</DropdownMenuLabel>
						{table
							.getAllColumns()
							.filter((column: any) => column.getCanHide())
							.map((column: any) => (
								<DropdownMenuCheckboxItem
									key={column.id}
									className="capitalize"
									checked={column.getIsVisible()}
									onCheckedChange={(value) => column.toggleVisibility(!!value)}
									onSelect={(event) => event.preventDefault()}
								>
									{column.id}
								</DropdownMenuCheckboxItem>
							))}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</motion.div>
	);
}

// Filter Dropdown Component
function FilterDropdown({
	title,
	column,
	options,
	id,
	t,
}: {
	title: string;
	column: any;
	options: string[];
	id: string;
	t: (key: string) => string;
}) {
	const selectedValues = useMemo(() => {
		const filterValue = column?.getFilterValue() as string[];
		return filterValue ?? [];
	}, [column?.getFilterValue]);

	const handleValueChange = (checked: boolean, value: string) => {
		const filterValue = column?.getFilterValue() as string[];
		const newFilterValue = filterValue ? [...filterValue] : [];

		if (checked) {
			newFilterValue.push(value);
		} else {
			const index = newFilterValue.indexOf(value);
			if (index > -1) {
				newFilterValue.splice(index, 1);
			}
		}

		column?.setFilterValue(newFilterValue.length ? newFilterValue : undefined);
	};

	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button variant="outline">
					<Filter className="-ms-1 me-2 opacity-60" size={16} strokeWidth={2} />
					{title}
					{selectedValues.length > 0 && (
						<span className="-me-1 ms-3 inline-flex h-5 max-h-full items-center rounded border border-border bg-background px-1 font-[inherit] text-[0.625rem] font-medium text-muted-foreground/70">
							{selectedValues.length}
						</span>
					)}
				</Button>
			</PopoverTrigger>
			<PopoverContent className="min-w-36 p-3" align="start">
				<div className="space-y-3">
					<div className="text-xs font-medium text-muted-foreground">
						{t("filter_by")} {title}
					</div>
					<div className="space-y-2">
						{options.map((value, i) => (
							<div key={value} className="flex items-center gap-2">
								<Checkbox
									id={`${id}-${i}`}
									checked={selectedValues.includes(value)}
									onCheckedChange={(checked: boolean) => handleValueChange(checked, value)}
								/>
								<Label htmlFor={`${id}-${i}`} className="text-sm font-normal">
									{value}
								</Label>
							</div>
						))}
					</div>
				</div>
			</PopoverContent>
		</Popover>
	);
}

// Logs Table Component
function LogsTable({
	table,
	logs,
	loading,
	error,
	onRefresh,
	id,
	t,
}: {
	table: any;
	logs: Log[];
	loading: boolean;
	error: string | null;
	onRefresh: () => void;
	id: string;
	t: (key: string, params?: any) => string;
}) {
	if (loading) {
		return (
			<motion.div
				className="rounded-md border"
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
			>
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-2">
						<div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
						<p className="text-sm text-muted-foreground">Loading logs...</p>
					</div>
				</div>
			</motion.div>
		);
	}

	if (error) {
		return (
			<motion.div
				className="rounded-md border"
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
			>
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-2">
						<AlertCircle className="h-8 w-8 text-destructive" />
						<p className="text-sm text-destructive">Error loading logs</p>
						<Button variant="outline" size="sm" onClick={onRefresh}>
							Retry
						</Button>
					</div>
				</div>
			</motion.div>
		);
	}

	if (logs.length === 0) {
		return (
			<motion.div
				className="rounded-md border"
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
			>
				<div className="flex h-[400px] w-full items-center justify-center">
					<div className="flex flex-col items-center gap-2">
						<Terminal className="h-8 w-8 text-muted-foreground" />
						<p className="text-sm text-muted-foreground">{t("no_logs")}</p>
					</div>
				</div>
			</motion.div>
		);
	}

	return (
		<>
			<motion.div
				className="rounded-md border overflow-hidden"
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ delay: 0.3 }}
			>
				<Table className="table-fixed">
					<TableHeader>
						{table.getHeaderGroups().map((headerGroup: any) => (
							<TableRow key={headerGroup.id} className="hover:bg-transparent">
								{headerGroup.headers.map((header: any) => (
									<TableHead
										key={header.id}
										style={{ width: `${header.getSize()}px` }}
										className={cn(
											"h-12 px-4 py-3",
											// keep Created At header from wrapping and align it
											header.column.id === "created_at" ? "whitespace-nowrap text-right" : ""
										)}
									>
										{header.isPlaceholder ? null : header.column.getCanSort() ? (
											<Button
												variant="ghost"
												size="sm"
												className={cn(
													"flex h-full cursor-pointer select-none items-center justify-between gap-2"
												)}
												onClick={header.column.getToggleSortingHandler()}
											>
												{flexRender(header.column.columnDef.header, header.getContext())}
												{{
													asc: <ChevronUp className="shrink-0 opacity-60" size={16} />,
													desc: <ChevronDown className="shrink-0 opacity-60" size={16} />,
												}[header.column.getIsSorted() as string] ?? null}
											</Button>
										) : (
											flexRender(header.column.columnDef.header, header.getContext())
										)}
									</TableHead>
								))}
							</TableRow>
						))}
					</TableHeader>
					<TableBody>
						<AnimatePresence mode="popLayout">
							{table.getRowModel().rows?.length ? (
								table.getRowModel().rows.map((row: any, index: number) => (
									<motion.tr
										key={row.id}
										initial={{ opacity: 0, y: 10 }}
										animate={{
											opacity: 1,
											y: 0,
											transition: {
												type: "spring",
												stiffness: 300,
												damping: 30,
												delay: index * 0.03,
											},
										}}
										exit={{ opacity: 0, y: -10 }}
										className={cn(
											"border-b transition-colors hover:bg-muted/50",
											row.getIsSelected() ? "bg-muted/50" : ""
										)}
									>
										{row.getVisibleCells().map((cell: any) => {
											const isCreatedAt = cell.column.id === "created_at";
											const isMessage = cell.column.id === "message";
											return (
												<TableCell
													key={cell.id}
													className={cn(
														"px-4 py-3 align-middle overflow-hidden",
														isCreatedAt
															? "whitespace-nowrap text-xs text-muted-foreground text-right"
															: "",
														isMessage ? "overflow-hidden" : ""
													)}
												>
													{flexRender(cell.column.columnDef.cell, cell.getContext())}
												</TableCell>
											);
										})}
									</motion.tr>
								))
							) : (
								<TableRow>
									<TableCell colSpan={columns.length} className="h-24 text-center">
										{t("no_logs")}
									</TableCell>
								</TableRow>
							)}
						</AnimatePresence>
					</TableBody>
				</Table>
			</motion.div>

			{/* Pagination */}
			<LogsPagination table={table} id={id} t={t} />
		</>
	);
}

// Pagination Component
function LogsPagination({ table, id, t }: { table: any; id: string; t: (key: string) => string }) {
	return (
		<div className="flex items-center justify-between gap-8 mt-6">
			<motion.div
				className="flex items-center gap-3"
				initial={{ opacity: 0, x: -20 }}
				animate={{ opacity: 1, x: 0 }}
			>
				<Label htmlFor={id} className="max-sm:sr-only">
					{t("rows_per_page")}
				</Label>
				<Select
					value={table.getState().pagination.pageSize.toString()}
					onValueChange={(value) => table.setPageSize(Number(value))}
				>
					<SelectTrigger id={id} className="w-fit whitespace-nowrap">
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						{[10, 20, 50, 100].map((pageSize) => (
							<SelectItem key={pageSize} value={pageSize.toString()}>
								{pageSize}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</motion.div>

			<motion.div
				className="flex grow justify-end whitespace-nowrap text-sm text-muted-foreground"
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ delay: 0.2 }}
			>
				<p className="whitespace-nowrap text-sm text-muted-foreground">
					<span className="text-foreground">
						{table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1}-
						{Math.min(
							table.getState().pagination.pageIndex * table.getState().pagination.pageSize +
								table.getState().pagination.pageSize,
							table.getRowCount()
						)}
					</span>{" "}
					of <span className="text-foreground">{table.getRowCount()}</span>
				</p>
			</motion.div>

			<div>
				<Pagination>
					<PaginationContent>
						<PaginationItem>
							<Button
								size="icon"
								variant="outline"
								onClick={() => table.firstPage()}
								disabled={!table.getCanPreviousPage()}
							>
								<ChevronFirst size={16} />
							</Button>
						</PaginationItem>
						<PaginationItem>
							<Button
								size="icon"
								variant="outline"
								onClick={() => table.previousPage()}
								disabled={!table.getCanPreviousPage()}
							>
								<ChevronLeft size={16} />
							</Button>
						</PaginationItem>
						<PaginationItem>
							<Button
								size="icon"
								variant="outline"
								onClick={() => table.nextPage()}
								disabled={!table.getCanNextPage()}
							>
								<ChevronRight size={16} />
							</Button>
						</PaginationItem>
						<PaginationItem>
							<Button
								size="icon"
								variant="outline"
								onClick={() => table.lastPage()}
								disabled={!table.getCanNextPage()}
							>
								<ChevronLast size={16} />
							</Button>
						</PaginationItem>
					</PaginationContent>
				</Pagination>
			</div>
		</div>
	);
}

// Row Actions Component
function LogRowActions({ row, t }: { row: Row<Log>; t: (key: string) => string }) {
	const [isOpen, setIsOpen] = useState(false);
	const [isDeleting, setIsDeleting] = useState(false);
	const { deleteLog, refreshLogs } = useContext(LogsContext)!;
	const log = row.original;

	const handleDelete = async () => {
		setIsDeleting(true);
		try {
			await deleteLog(log.id);
			toast.success(t("log_deleted_success"));
			await refreshLogs();
		} catch (error) {
			console.error("Error deleting log:", error);
			toast.error(t("log_deleted_error"));
		} finally {
			setIsDeleting(false);
			setIsOpen(false);
		}
	};

	return (
		<div className="flex justify-end">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="ghost" className="h-8 w-8 p-0">
						<MoreHorizontal className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<JsonMetadataViewer
						title={`Log ${log.id} - Metadata`}
						metadata={log.log_metadata}
						trigger={
							<DropdownMenuItem onSelect={(e) => e.preventDefault()}>
								{t("view_metadata")}
							</DropdownMenuItem>
						}
					/>
					<DropdownMenuSeparator />
					<AlertDialog open={isOpen} onOpenChange={setIsOpen}>
						<AlertDialogTrigger asChild>
							<DropdownMenuItem
								className="text-destructive focus:text-destructive"
								onSelect={(e) => {
									e.preventDefault();
									setIsOpen(true);
								}}
							>
								{t("delete")}
							</DropdownMenuItem>
						</AlertDialogTrigger>
						<AlertDialogContent>
							<AlertDialogHeader>
								<AlertDialogTitle>{t("confirm_delete_log_title")}</AlertDialogTitle>
								<AlertDialogDescription>{t("confirm_delete_log_desc")}</AlertDialogDescription>
							</AlertDialogHeader>
							<AlertDialogFooter>
								<AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
								<AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
									{isDeleting ? t("deleting") : t("delete")}
								</AlertDialogAction>
							</AlertDialogFooter>
						</AlertDialogContent>
					</AlertDialog>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
