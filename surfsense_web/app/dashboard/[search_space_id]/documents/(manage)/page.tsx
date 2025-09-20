"use client";

import { motion } from "framer-motion";
import { useParams } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";
import { toast } from "sonner";

import { useDocuments } from "@/hooks/use-documents";

import { DocumentsFilters } from "./components/DocumentsFilters";
import { DocumentsTableShell, type SortKey } from "./components/DocumentsTableShell";
import { PaginationControls } from "./components/PaginationControls";
import type { ColumnVisibility, Document } from "./components/types";

function useDebounced<T>(value: T, delay = 250) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(t);
	}, [value, delay]);
	return debounced;
}

export default function DocumentsTable() {
	const id = useId();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const [pageIndex, setPageIndex] = useState(0);
	const [pageSize, setPageSize] = useState(100); // Increased page size for better performance
	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 250);
	const [activeTypes, setActiveTypes] = useState<string[]>([]);
	const [columnVisibility, setColumnVisibility] = useState<ColumnVisibility>({
		title: true,
		document_type: true,
		content: true,
		created_at: true,
	});
	const [sortKey, setSortKey] = useState<SortKey>("title");
	const [sortDesc, setSortDesc] = useState(false);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

	// Calculate skip value for pagination
	const skip = pageIndex * pageSize;

	const { documents, loading, error, refreshDocuments, deleteDocument } = useDocuments(
		searchSpaceId,
		false,
		skip,
		pageSize
	);

	const [data, setData] = useState<Document[]>([]);

	useEffect(() => {
		if (documents) setData(documents as Document[]);
	}, [documents]);

	// For server-side pagination, we apply client-side filtering to the current page data
	// Note: This is a simplified approach. For production, you might want to implement server-side filtering
	const filtered = useMemo(() => {
		let result = data;
		if (debouncedSearch.trim()) {
			const q = debouncedSearch.toLowerCase();
			result = result.filter((d) => d.title.toLowerCase().includes(q));
		}
		if (activeTypes.length > 0) {
			result = result.filter((d) => activeTypes.includes(d.document_type));
		}
		return result;
	}, [data, debouncedSearch, activeTypes]);

	// For server-side pagination, we show the filtered results from current page
	// Total count is estimated based on current page size (this could be improved with a count endpoint)
	const pageDocs = filtered;
	const total = pageSize * (pageIndex + 1); // Estimated total, could be improved with actual count

	const onToggleType = (type: string, checked: boolean) => {
		setActiveTypes((prev) => (checked ? [...prev, type] : prev.filter((t) => t !== type)));
		setPageIndex(0);
	};

	// Reset to first page when search changes
	useEffect(() => {
		setPageIndex(0);
	}, [debouncedSearch]);

	const onToggleColumn = (id: keyof ColumnVisibility, checked: boolean) => {
		setColumnVisibility((prev) => ({ ...prev, [id]: checked }));
	};

	const onBulkDelete = async () => {
		if (selectedIds.size === 0) {
			toast.error("No rows selected");
			return;
		}
		try {
			const results = await Promise.all(Array.from(selectedIds).map((id) => deleteDocument?.(id)));
			const okCount = results.filter((r) => r === true).length;
			if (okCount === selectedIds.size)
				toast.success(`Successfully deleted ${okCount} document(s)`);
			else toast.error("Some documents could not be deleted");
			await refreshDocuments?.();
			setSelectedIds(new Set());
		} catch (e) {
			console.error(e);
			toast.error("Error deleting documents");
		}
	};

	useEffect(() => {
		const mq = window.matchMedia("(max-width: 768px)");
		const apply = (isSmall: boolean) => {
			setColumnVisibility((prev) => ({ ...prev, content: !isSmall, created_at: !isSmall }));
		};
		apply(mq.matches);
		const onChange = (e: MediaQueryListEvent) => apply(e.matches);
		mq.addEventListener("change", onChange);
		return () => mq.removeEventListener("change", onChange);
	}, []);

	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3 }}
			className="w-full px-6 py-4"
		>
			<DocumentsFilters
				allDocuments={data}
				visibleDocuments={pageDocs}
				selectedIds={selectedIds}
				onSearch={setSearch}
				searchValue={search}
				onBulkDelete={onBulkDelete}
				onToggleType={onToggleType}
				activeTypes={activeTypes}
				columnVisibility={columnVisibility}
				onToggleColumn={onToggleColumn}
			/>

			<DocumentsTableShell
				documents={pageDocs}
				loading={!!loading}
				error={!!error}
				onRefresh={async () => {
					await (refreshDocuments?.() ?? Promise.resolve());
				}}
				selectedIds={selectedIds}
				setSelectedIds={setSelectedIds}
				columnVisibility={columnVisibility}
				deleteDocument={(id) => deleteDocument?.(id) ?? Promise.resolve(false)}
				sortKey={sortKey}
				sortDesc={sortDesc}
				onSortChange={(key) => {
					if (sortKey === key) setSortDesc((v) => !v);
					else {
						setSortKey(key);
						setSortDesc(false);
					}
				}}
			/>

			<PaginationControls
				pageIndex={pageIndex}
				pageSize={pageSize}
				total={total}
				onPageSizeChange={(s) => {
					setPageSize(s);
					setPageIndex(0);
				}}
				onFirst={() => setPageIndex(0)}
				onPrev={() => setPageIndex((i) => Math.max(0, i - 1))}
				onNext={() => setPageIndex((i) => i + 1)}
				onLast={() => setPageIndex(Math.max(0, Math.ceil(total / pageSize) - 1))}
				canPrev={pageIndex > 0}
				canNext={pageDocs.length === pageSize} // Show next if current page is full
				id={id}
			/>
		</motion.div>
	);
}

export { DocumentsTable };
