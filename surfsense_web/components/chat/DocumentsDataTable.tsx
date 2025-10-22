"use client";

import {
	type ColumnDef,
	flexRender,
	getCoreRowModel,
	type SortingState,
	useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, Calendar, FileText, Filter, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { type Document, type DocumentType, useDocuments } from "@/hooks/use-documents";

interface DocumentsDataTableProps {
	searchSpaceId: number;
	onSelectionChange: (documents: Document[]) => void;
	onDone: () => void;
	initialSelectedDocuments?: Document[];
}

function useDebounced<T>(value: T, delay = 300) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(t);
	}, [value, delay]);
	return debounced;
}

const columns: ColumnDef<Document>[] = [
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
	searchSpaceId,
	onSelectionChange,
	onDone,
	initialSelectedDocuments = [],
}: DocumentsDataTableProps) {
	const [sorting, setSorting] = useState<SortingState>([]);
	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 300);
	const [documentTypeFilter, setDocumentTypeFilter] = useState<string[]>([]);
	const [pageIndex, setPageIndex] = useState(0);
	const [pageSize, setPageSize] = useState(10);
	const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});

	// Use server-side pagination, search, and filtering
	const { documents, total, loading, fetchDocuments, searchDocuments, getDocumentTypeCounts } =
		useDocuments(searchSpaceId, {
			page: pageIndex,
			pageSize: pageSize,
		});

	// Fetch document type counts on mount
	useEffect(() => {
		if (searchSpaceId && getDocumentTypeCounts) {
			getDocumentTypeCounts().then(setTypeCounts);
		}
	}, [searchSpaceId, getDocumentTypeCounts]);

	// Refetch when pagination changes or when search/filters change
	useEffect(() => {
		if (searchSpaceId) {
			if (debouncedSearch.trim()) {
				searchDocuments?.(
					debouncedSearch,
					pageIndex,
					pageSize,
					documentTypeFilter.length > 0 ? documentTypeFilter : undefined
				);
			} else {
				fetchDocuments?.(
					pageIndex,
					pageSize,
					documentTypeFilter.length > 0 ? documentTypeFilter : undefined
				);
			}
		}
	}, [
		pageIndex,
		pageSize,
		debouncedSearch,
		documentTypeFilter,
		searchSpaceId,
		fetchDocuments,
		searchDocuments,
	]);

	// Memoize initial row selection to prevent infinite loops
	const initialRowSelection = useMemo(() => {
		if (!initialSelectedDocuments.length) return {};

		const selection: Record<string, boolean> = {};
		initialSelectedDocuments.forEach((selectedDoc) => {
			selection[selectedDoc.id] = true;
		});
		return selection;
	}, [initialSelectedDocuments]);

	const [rowSelection, setRowSelection] = useState<Record<string, boolean>>(
		() => initialRowSelection
	);

	// Maintain a separate state for actually selected documents (across all pages)
	const [selectedDocumentsMap, setSelectedDocumentsMap] = useState<Map<number, Document>>(() => {
		const map = new Map<number, Document>();
		initialSelectedDocuments.forEach((doc) => map.set(doc.id, doc));
		return map;
	});

	// Track the last notified selection to avoid redundant parent calls
	const lastNotifiedSelection = useRef<string>("");

	// Update row selection only when initialSelectedDocuments changes (not rowSelection itself)
	useEffect(() => {
		const initialKeys = Object.keys(initialRowSelection);
		if (initialKeys.length === 0) return;

		const currentKeys = Object.keys(rowSelection);
		// Quick length check before expensive comparison
		if (currentKeys.length === initialKeys.length) {
			// Check if all keys match (order doesn't matter for Sets)
			const hasAllKeys = initialKeys.every((key) => rowSelection[key]);
			if (hasAllKeys) return;
		}

		setRowSelection(initialRowSelection);
	}, [initialRowSelection]); // Remove rowSelection from dependencies to prevent loop

	// Update the selected documents map when row selection changes
	useEffect(() => {
		if (!documents || documents.length === 0) return;

		setSelectedDocumentsMap((prev) => {
			const newMap = new Map(prev);
			let hasChanges = false;

			// Process only current page documents
			for (const doc of documents) {
				const docId = doc.id;
				const isSelected = rowSelection[docId.toString()];
				const wasInMap = newMap.has(docId);

				if (isSelected && !wasInMap) {
					newMap.set(docId, doc);
					hasChanges = true;
				} else if (!isSelected && wasInMap) {
					newMap.delete(docId);
					hasChanges = true;
				}
			}

			// Return same reference if no changes to avoid unnecessary re-renders
			return hasChanges ? newMap : prev;
		});
	}, [rowSelection, documents]);

	// Memoize selected documents array
	const selectedDocumentsArray = useMemo(() => {
		return Array.from(selectedDocumentsMap.values());
	}, [selectedDocumentsMap]);

	// Notify parent of selection changes only when content actually changes
	useEffect(() => {
		// Create a stable string representation for comparison
		const selectionKey = selectedDocumentsArray
			.map((d) => d.id)
			.sort()
			.join(",");

		// Skip if selection hasn't actually changed
		if (selectionKey === lastNotifiedSelection.current) return;

		lastNotifiedSelection.current = selectionKey;
		onSelectionChange(selectedDocumentsArray);
	}, [selectedDocumentsArray, onSelectionChange]);

	const table = useReactTable({
		data: documents || [],
		columns,
		getRowId: (row) => row.id.toString(),
		onSortingChange: setSorting,
		getCoreRowModel: getCoreRowModel(),
		onRowSelectionChange: setRowSelection,
		manualPagination: true,
		pageCount: Math.ceil(total / pageSize),
		state: { sorting, rowSelection, pagination: { pageIndex, pageSize } },
	});

	const handleClearAll = useCallback(() => {
		setRowSelection({});
		setSelectedDocumentsMap(new Map());
	}, []);

	const handleSelectPage = useCallback(() => {
		const currentPageRows = table.getRowModel().rows;
		const newSelection = { ...rowSelection };
		currentPageRows.forEach((row) => {
			newSelection[row.id] = true;
		});
		setRowSelection(newSelection);
	}, [table, rowSelection]);

	const handleToggleType = useCallback((type: string, checked: boolean) => {
		setDocumentTypeFilter((prev) => {
			if (checked) {
				return [...prev, type];
			}
			return prev.filter((t) => t !== type);
		});
		setPageIndex(0); // Reset to first page when filter changes
	}, []);

	const selectedCount = selectedDocumentsMap.size;

	// Get available document types from type counts (memoized)
	const availableTypes = useMemo(() => {
		const types = Object.keys(typeCounts);
		return types.length > 0 ? types.sort() : [];
	}, [typeCounts]);

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
							value={search}
							onChange={(event) => {
								setSearch(event.target.value);
								setPageIndex(0); // Reset to first page on search
							}}
							className="pl-10 text-sm"
						/>
					</div>
					<Popover>
						<PopoverTrigger asChild>
							<Button variant="outline" className="w-full sm:w-auto">
								<Filter className="mr-2 h-4 w-4 opacity-60" />
								Type
								{documentTypeFilter.length > 0 && (
									<span className="ml-2 inline-flex h-5 items-center rounded border border-border bg-background px-1.5 text-[0.625rem] font-medium text-muted-foreground/70">
										{documentTypeFilter.length}
									</span>
								)}
							</Button>
						</PopoverTrigger>
						<PopoverContent className="w-64 p-3" align="start">
							<div className="space-y-3">
								<div className="text-xs font-medium text-muted-foreground">Filter by Type</div>
								<div className="space-y-2 max-h-[300px] overflow-y-auto">
									{availableTypes.map((type) => (
										<div key={type} className="flex items-center gap-2">
											<Checkbox
												id={`type-${type}`}
												checked={documentTypeFilter.includes(type)}
												onCheckedChange={(checked) => handleToggleType(type, !!checked)}
											/>
											<Label
												htmlFor={`type-${type}`}
												className="flex grow justify-between gap-2 font-normal text-sm cursor-pointer"
											>
												<span>{type.replace(/_/g, " ")}</span>
												<span className="text-xs text-muted-foreground">{typeCounts[type]}</span>
											</Label>
										</div>
									))}
								</div>
								{documentTypeFilter.length > 0 && (
									<Button
										variant="ghost"
										size="sm"
										className="w-full text-xs"
										onClick={() => {
											setDocumentTypeFilter([]);
											setPageIndex(0);
										}}
									>
										Clear Filters
									</Button>
								)}
							</div>
						</PopoverContent>
					</Popover>
				</div>

				{/* Action Controls Row */}
				<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
					<div className="flex flex-col sm:flex-row sm:items-center gap-2">
						<span className="text-sm text-muted-foreground whitespace-nowrap">
							{selectedCount} selected {loading && "· Loading..."}
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
								disabled={loading}
							>
								Select Page
							</Button>
							<Select
								value={pageSize.toString()}
								onValueChange={(v) => {
									setPageSize(Number(v));
									setPageIndex(0);
								}}
							>
								<SelectTrigger className="w-[100px] h-8 text-xs">
									<SelectValue>{pageSize} per page</SelectValue>
								</SelectTrigger>
								<SelectContent>
									{[10, 25, 50, 100].map((size) => (
										<SelectItem key={size} value={size.toString()}>
											{size} per page
										</SelectItem>
									))}
								</SelectContent>
							</Select>
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
					{loading ? (
						<div className="flex items-center justify-center h-full">
							<div className="text-center space-y-2">
								<div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto" />
								<p className="text-sm text-muted-foreground">Loading documents...</p>
							</div>
						</div>
					) : (
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
					)}
				</div>
			</div>

			{/* Footer Pagination */}
			<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs sm:text-sm text-muted-foreground border-t pt-3 md:pt-4 flex-shrink-0">
				<div className="text-center sm:text-left">
					Showing {pageIndex * pageSize + 1} to {Math.min((pageIndex + 1) * pageSize, total)} of{" "}
					{total} documents
				</div>
				<div className="flex items-center justify-center sm:justify-end space-x-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
						disabled={pageIndex === 0 || loading}
						className="text-xs sm:text-sm"
					>
						Previous
					</Button>
					<div className="flex items-center space-x-1 text-xs sm:text-sm">
						<span>Page</span>
						<strong>{pageIndex + 1}</strong>
						<span>of</span>
						<strong>{Math.ceil(total / pageSize)}</strong>
					</div>
					<Button
						variant="outline"
						size="sm"
						onClick={() => setPageIndex((p) => p + 1)}
						disabled={pageIndex >= Math.ceil(total / pageSize) - 1 || loading}
						className="text-xs sm:text-sm"
					>
						Next
					</Button>
				</div>
			</div>
		</div>
	);
}
