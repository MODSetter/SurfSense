"use client";

import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
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
	const t = useTranslations("documents");
	const id = useId();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 250);
	const [activeTypes, setActiveTypes] = useState<string[]>([]);
	const [columnVisibility, setColumnVisibility] = useState<ColumnVisibility>({
		title: true,
		document_type: true,
		content: true,
		created_at: true,
	});
	const [pageIndex, setPageIndex] = useState(0);
	const [pageSize, setPageSize] = useState(50);
	const [sortKey, setSortKey] = useState<SortKey>("title");
	const [sortDesc, setSortDesc] = useState(false);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});

	// Use server-side pagination, search, and filtering
	const {
		documents,
		total,
		loading,
		error,
		fetchDocuments,
		searchDocuments,
		deleteDocument,
		getDocumentTypeCounts,
	} = useDocuments(searchSpaceId, {
		page: pageIndex,
		pageSize: pageSize,
	});

	// Fetch document type counts on mount and when search space changes
	useEffect(() => {
		if (searchSpaceId && getDocumentTypeCounts) {
			getDocumentTypeCounts().then(setTypeCounts);
		}
	}, [searchSpaceId, getDocumentTypeCounts]);

	// Refetch when pagination changes or when search/filters change
	useEffect(() => {
		if (searchSpaceId) {
			if (debouncedSearch.trim()) {
				// Use search endpoint if there's a search query
				searchDocuments?.(
					debouncedSearch,
					pageIndex,
					pageSize,
					activeTypes.length > 0 ? activeTypes : undefined
				);
			} else {
				// Use regular fetch if no search
				fetchDocuments?.(pageIndex, pageSize, activeTypes.length > 0 ? activeTypes : undefined);
			}
		}
	}, [
		pageIndex,
		pageSize,
		debouncedSearch,
		activeTypes,
		searchSpaceId,
		fetchDocuments,
		searchDocuments,
	]);

	// Display server-filtered results directly
	const displayDocs = documents || [];
	const displayTotal = total;
	const pageStart = pageIndex * pageSize;
	const pageEnd = Math.min(pageStart + pageSize, displayTotal);

	const onToggleType = (type: string, checked: boolean) => {
		setActiveTypes((prev) => (checked ? [...prev, type] : prev.filter((t) => t !== type)));
		setPageIndex(0);
	};

	const onToggleColumn = (id: keyof ColumnVisibility, checked: boolean) => {
		setColumnVisibility((prev) => ({ ...prev, [id]: checked }));
	};

	const refreshCurrentView = useCallback(async () => {
		if (debouncedSearch.trim()) {
			await searchDocuments?.(
				debouncedSearch,
				pageIndex,
				pageSize,
				activeTypes.length > 0 ? activeTypes : undefined
			);
		} else {
			await fetchDocuments?.(pageIndex, pageSize, activeTypes.length > 0 ? activeTypes : undefined);
		}
	}, [debouncedSearch, pageIndex, pageSize, activeTypes, searchDocuments, fetchDocuments]);

	const onBulkDelete = async () => {
		if (selectedIds.size === 0) {
			toast.error(t("no_rows_selected"));
			return;
		}
		try {
			const results = await Promise.all(Array.from(selectedIds).map((id) => deleteDocument?.(id)));
			const okCount = results.filter((r) => r === true).length;
			if (okCount === selectedIds.size)
				toast.success(t("delete_success_count", { count: okCount }));
			else toast.error(t("delete_partial_failed"));
			// Refetch the current page with appropriate method
			await refreshCurrentView();
			setSelectedIds(new Set());
		} catch (e) {
			console.error(e);
			toast.error(t("delete_error"));
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
				typeCounts={typeCounts}
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
				documents={displayDocs}
				loading={!!loading}
				error={!!error}
				onRefresh={refreshCurrentView}
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
				total={displayTotal}
				onPageSizeChange={(s) => {
					setPageSize(s);
					setPageIndex(0);
				}}
				onFirst={() => setPageIndex(0)}
				onPrev={() => setPageIndex((i) => Math.max(0, i - 1))}
				onNext={() => setPageIndex((i) => (pageEnd < displayTotal ? i + 1 : i))}
				onLast={() => setPageIndex(Math.max(0, Math.ceil(displayTotal / pageSize) - 1))}
				canPrev={pageIndex > 0}
				canNext={pageEnd < displayTotal}
				id={id}
			/>
		</motion.div>
	);
}

export { DocumentsTable };
