"use client";

import {
	type ColumnDef,
	type ColumnFiltersState,
	flexRender,
	getCoreRowModel,
	getFilteredRowModel,
	getPaginationRowModel,
	getSortedRowModel,
	type SortingState,
	useReactTable,
	type VisibilityState,
} from "@tanstack/react-table";
import { ArrowUpDown, Calendar, FileText, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
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
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { Document, DocumentType } from "@/hooks/use-documents";

interface DocumentsDataTableProps {
	documents: Document[];
	onSelectionChange: (documents: Document[]) => void;
	onDone: () => void;
	initialSelectedDocuments?: Document[];
	pageIndex?: number;
	pageSize?: number;
	onPageIndexChange?: (pageIndex: number) => void;
	onPageSizeChange?: (pageSize: number) => void;
	canNext?: boolean;
}

// Combine EnumConnectorName with additional document types
const DOCUMENT_TYPES: (string | "ALL")[] = [
	"ALL",
	"FILE",
	"EXTENSION",
	"CRAWLED_URL",
	"YOUTUBE_VIDEO",
	...Object.values(EnumConnectorName),
];

const columns: ColumnDef<Document>[] = [
	{
		id: "select",
		header: ({ table }) => (
			<Checkbox
				checked={
					table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")
				}
				onCheckedChange={(value) => {
					table.toggleAllPageRowsSelected(!!value);
				}}
				aria-label="Select all"
			/>
		),
		cell: ({ row }) => (
			<Checkbox
				checked={row.getIsSelected()}
				onCheckedChange={(value) => {
					row.toggleSelected(!!value);
				}}
				aria-label="Select row"
			/>
		),
		enableSorting: false,
		enableHiding: false,
		size: 40,
	},
	{
		accessorKey: "title",
		header: ({ column }) => (
			<Button
				variant="ghost"
				onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
				className="h-8 px-1 sm:px-2 font-medium text-left justify-start"
			>
				<FileText className="mr-1 sm:mr-2 h-3 w-3 sm:h-4 sm:w-4 flex-shrink-0" />
				<span className="hidden sm:inline">Title</span>
				<span className="sm:hidden">Doc</span>
				<ArrowUpDown className="ml-1 sm:ml-2 h-3 w-3 sm:h-4 sm:w-4 flex-shrink-0" />
			</Button>
		),
		cell: ({ row }) => {
			const title = row.getValue("title") as string;
			return (
				<div
					className="font-medium max-w-[120px] sm:max-w-[250px] truncate text-xs sm:text-sm"
					title={title}
				>
					{title}
				</div>
			);
		},
	},
	{
		accessorKey: "document_type",
		header: "Type",
		cell: ({ row }) => {
			const type = row.getValue("document_type") as DocumentType;
			return (
				<div className="flex items-center gap-2" title={type}>
					<span className="text-primary">{getConnectorIcon(type)}</span>
				</div>
			);
		},
		size: 80,
		meta: {
			className: "hidden sm:table-cell",
		},
	},
	{
		accessorKey: "content",
		header: "Preview",
		cell: ({ row }) => {
			const content = row.getValue("content") as string;
			return (
				<div
					className="text-muted-foreground max-w-[150px] sm:max-w-[350px] truncate text-[10px] sm:text-sm"
					title={content}
				>
					<span className="sm:hidden">{content.substring(0, 30)}...</span>
					<span className="hidden sm:inline">{content.substring(0, 100)}...</span>
				</div>
			);
		},
		enableSorting: false,
		meta: {
			className: "hidden md:table-cell",
		},
	},
	{
		accessorKey: "created_at",
		header: ({ column }) => (
			<Button
				variant="ghost"
				onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
				className="h-8 px-1 sm:px-2 font-medium"
			>
				<Calendar className="mr-1 sm:mr-2 h-3 w-3 sm:h-4 sm:w-4 flex-shrink-0" />
				<span className="hidden sm:inline">Created</span>
				<span className="sm:hidden">Date</span>
				<ArrowUpDown className="ml-1 sm:ml-2 h-3 w-3 sm:h-4 sm:w-4 flex-shrink-0" />
			</Button>
		),
		cell: ({ row }) => {
			const date = new Date(row.getValue("created_at"));
			return (
				<div className="text-xs sm:text-sm whitespace-nowrap">
					<span className="hidden sm:inline">
						{date.toLocaleDateString("en-US", {
							month: "short",
							day: "numeric",
							year: "numeric",
						})}
					</span>
					<span className="sm:hidden">
						{date.toLocaleDateString("en-US", {
							month: "numeric",
							day: "numeric",
						})}
					</span>
				</div>
			);
		},
		size: 80,
	},
];

export function DocumentsDataTable({
	documents,
	onSelectionChange,
	onDone,
	initialSelectedDocuments = [],
	pageIndex = 0,
	pageSize = 100,
	onPageIndexChange,
	onPageSizeChange,
	canNext = false,
}: DocumentsDataTableProps) {
	const [sorting, setSorting] = useState<SortingState>([]);
	const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
	const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
	const [documentTypeFilter, setDocumentTypeFilter] = useState<string | "ALL">("ALL");

	// Memoize initial row selection to prevent infinite loops
	const initialRowSelection = useMemo(() => {
		if (!documents.length || !initialSelectedDocuments.length) return {};

		const selection: Record<string, boolean> = {};
		initialSelectedDocuments.forEach((selectedDoc) => {
			// Find the document in the current documents array to get the correct row ID
			const docInCurrentList = documents.find(doc => doc.id === selectedDoc.id);
			if (docInCurrentList) {
				selection[docInCurrentList.id.toString()] = true;
			}
		});
		return selection;
	}, [documents, initialSelectedDocuments]);

	const [rowSelection, setRowSelection] = useState<Record<string, boolean>>(() => initialRowSelection);

	// Update row selection when initial selection changes
	useEffect(() => {
		setRowSelection(initialRowSelection);
	}, [initialRowSelection]);

	const filteredDocuments = useMemo(() => {
		if (documentTypeFilter === "ALL") return documents;
		return documents.filter((doc) => doc.document_type === documentTypeFilter);
	}, [documents, documentTypeFilter]);

	const table = useReactTable({
		data: filteredDocuments,
		columns,
		getRowId: (row) => row.id.toString(),
		onSortingChange: setSorting,
		onColumnFiltersChange: setColumnFilters,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel(),
		onColumnVisibilityChange: setColumnVisibility,
		onRowSelectionChange: setRowSelection,
		// Disable internal pagination since we're handling it at the parent level
		manualPagination: true,
		pageCount: -1,
		enableRowSelection: true,
		state: { sorting, columnFilters, columnVisibility, rowSelection },
	});

	useEffect(() => {
		const selectedRows = table.getFilteredSelectedRowModel().rows;
		const selectedDocuments = selectedRows.map((row) => row.original);
		onSelectionChange(selectedDocuments);
	}, [rowSelection, table]);

	const handleClearAll = () => setRowSelection({});

	const handleSelectPage = () => {
		const currentPageRows = table.getRowModel().rows;
		const newSelection = { ...rowSelection };
		currentPageRows.forEach((row) => {
			newSelection[row.id] = true;
		});
		setRowSelection(newSelection);
	};

	const handleSelectAllFiltered = () => {
		const allFilteredRows = table.getFilteredRowModel().rows;
		const newSelection: Record<string, boolean> = {};
		allFilteredRows.forEach((row) => {
			newSelection[row.id] = true;
		});
		setRowSelection(newSelection);
	};

	const selectedCount = table.getFilteredSelectedRowModel().rows.length;
	const totalFiltered = table.getFilteredRowModel().rows.length;


	return (
		<div className="flex flex-col h-full space-y-3 md:space-y-4">
			{/* Header Controls */}
			<div className="space-y-3 md:space-y-4 flex-shrink-0">
				{/* Search and Filter Row */}
				<div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
					<div className="relative flex-1 max-w-full sm:max-w-sm">
						<Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
						<Input
							placeholder="Search documents..."
							value={(table.getColumn("title")?.getFilterValue() as string) ?? ""}
							onChange={(event) => table.getColumn("title")?.setFilterValue(event.target.value)}
							className="pl-10 text-sm"
						/>
					</div>
					<Select
						value={documentTypeFilter}
						onValueChange={(value) => setDocumentTypeFilter(value as string | "ALL")}
					>
						<SelectTrigger className="w-full sm:w-[180px]">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{DOCUMENT_TYPES.map((type) => (
								<SelectItem key={type} value={type}>
									{type === "ALL" ? "All Types" : type.replace(/_/g, " ")}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>

				{/* Action Controls Row */}
				<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
					<div className="flex flex-col sm:flex-row sm:items-center gap-2">
						<span className="text-sm text-muted-foreground whitespace-nowrap">
							{selectedCount} of {totalFiltered} selected
						</span>
						<div className="hidden sm:block h-4 w-px bg-border mx-2" />
						<div className="flex items-center gap-2 flex-wrap">
							<Button
								variant="ghost"
								size="sm"
								onClick={handleClearAll}
								disabled={selectedCount === 0}
								className="text-xs sm:text-sm"
							>
								Clear All
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={handleSelectPage}
								className="text-xs sm:text-sm"
							>
								Select Page
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={handleSelectAllFiltered}
								className="text-xs sm:text-sm hidden sm:inline-flex"
							>
								Select All Filtered
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={handleSelectAllFiltered}
								className="text-xs sm:hidden"
							>
								Select All
							</Button>
						</div>
					</div>
					<Button
						onClick={onDone}
						disabled={selectedCount === 0}
						className="w-full sm:w-auto sm:min-w-[100px]"
					>
						Done ({selectedCount})
					</Button>
				</div>
			</div>

			{/* Table Container */}
			<div className="border rounded-lg flex-1 min-h-0 overflow-hidden bg-background">
				<div className="overflow-auto h-full">
					<Table>
						<TableHeader className="sticky top-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-10">
							{table.getHeaderGroups().map((headerGroup) => (
								<TableRow key={headerGroup.id} className="border-b">
									{headerGroup.headers.map((header) => (
										<TableHead key={header.id} className="h-12 text-xs sm:text-sm">
											{header.isPlaceholder
												? null
												: flexRender(header.column.columnDef.header, header.getContext())}
										</TableHead>
									))}
								</TableRow>
							))}
						</TableHeader>
						<TableBody>
							{table.getRowModel().rows?.length ? (
								table.getRowModel().rows.map((row) => (
									<TableRow
										key={row.id}
										data-state={row.getIsSelected() && "selected"}
										className="hover:bg-muted/30"
									>
										{row.getVisibleCells().map((cell) => (
											<TableCell key={cell.id} className="py-3 text-xs sm:text-sm">
												{flexRender(cell.column.columnDef.cell, cell.getContext())}
											</TableCell>
										))}
									</TableRow>
								))
							) : (
								<TableRow>
									<TableCell
										colSpan={columns.length}
										className="h-32 text-center text-muted-foreground text-sm"
									>
										No documents found.
									</TableCell>
								</TableRow>
							)}
						</TableBody>
					</Table>
				</div>
			</div>

			{/* Footer Pagination */}
			<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs sm:text-sm text-muted-foreground border-t pt-3 md:pt-4 flex-shrink-0">
				<div className="text-center sm:text-left">
					Showing {pageIndex * pageSize + 1} to{" "}
					{Math.min((pageIndex + 1) * pageSize, pageIndex * pageSize + documents.length)} of{" "}
					{canNext
						? `${(pageIndex + 1) * pageSize}+`
						: `${pageIndex * pageSize + documents.length}`}{" "}
					documents
				</div>
				<div className="flex items-center justify-center sm:justify-end space-x-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => onPageIndexChange?.(pageIndex - 1)}
						disabled={pageIndex === 0}
						className="text-xs sm:text-sm"
					>
						Previous
					</Button>
					<div className="flex items-center space-x-1 text-xs sm:text-sm">
						<span>Page</span>
						<strong>{pageIndex + 1}</strong>
						{canNext && <span>+</span>}
					</div>
					<Button
						variant="outline"
						size="sm"
						onClick={() => onPageIndexChange?.(pageIndex + 1)}
						disabled={!canNext}
						className="text-xs sm:text-sm"
					>
						Next
					</Button>
				</div>
			</div>
		</div>
	);
}
