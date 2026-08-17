"use client";

import { useEffect, useMemo, useState } from "react";
import { type Column, DataGrid } from "react-data-grid";
import "react-data-grid/lib/styles.css";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { cannotPreviewMessage } from "./file-format";
import type { FileViewerProps } from "./model";
import {
	MAX_VIEWER_BYTES,
	ParseWorkbookError,
	parseWorkbook,
	type SheetView,
	type WorkbookView,
} from "./parse-workbook";
import { UnviewableFile } from "./unviewable-file";

function columnLabel(index: number): string {
	let n = index;
	let label = "";
	while (n >= 0) {
		label = String.fromCharCode((n % 26) + 65) + label;
		n = Math.floor(n / 26) - 1;
	}
	return label;
}

interface GridRow {
	readonly rowNumber: number;
	readonly [key: string]: string | number;
}

function SpreadsheetGrid({ sheet }: { sheet: SheetView }) {
	const { columns, rows } = useMemo(() => {
		const colCount = Math.max(1, ...sheet.cells.map((row) => row.length));
		const gridColumns: Column<GridRow>[] = [
			{
				key: "rowNumber",
				name: "",
				width: 48,
				frozen: true,
			},
			...Array.from(
				{ length: colCount },
				(_, col): Column<GridRow> => ({
					key: `column-${col}`,
					name: columnLabel(col),
				})
			),
		];
		const gridRows: GridRow[] = sheet.cells.map((row, index) =>
			Object.fromEntries([
				["rowNumber", index + 1],
				...row.map((cell, col) => [`column-${col}`, cell.text]),
			])
		);
		return { columns: gridColumns, rows: gridRows };
	}, [sheet]);

	return (
		<DataGrid
			aria-label={`${sheet.name} worksheet`}
			className="rdg-light h-full"
			columns={columns}
			rowKeyGetter={(row) => row.rowNumber}
			rows={rows}
			style={{ blockSize: "100%" }}
		/>
	);
}

function fallbackMessage(error: unknown, filename: string): string {
	if (error instanceof ParseWorkbookError) {
		if (error.code === "oversize") {
			return `${cannotPreviewMessage(filename)} (file is too large to preview)`;
		}
		return `${cannotPreviewMessage(filename)} (workbook could not be opened)`;
	}
	return cannotPreviewMessage(filename);
}

export default function XlsxViewer({ primary }: FileViewerProps) {
	const [view, setView] = useState<WorkbookView | null>(null);
	const [active, setActive] = useState(0);
	const [error, setError] = useState<unknown>(null);
	const [loading, setLoading] = useState(true);
	const [retryKey, setRetryKey] = useState(0);

	useEffect(() => {
		void retryKey;
		let cancelled = false;
		setLoading(true);
		setError(null);
		setView(null);

		(async () => {
			try {
				if (primary.size_bytes > MAX_VIEWER_BYTES) {
					throw new ParseWorkbookError(
						"oversize",
						`Workbook is too large to preview (${primary.size_bytes} bytes)`
					);
				}
				const response = await authenticatedFetch(buildBackendUrl(primary.content_url), {
					cache: "no-store",
					skipAuthRedirect: true,
				});
				if (!response.ok) {
					throw new Error(`Could not load workbook (${response.status})`);
				}
				const buffer = await response.arrayBuffer();
				const parsed = await parseWorkbook(buffer);
				if (!cancelled) {
					setView(parsed);
					setActive(0);
				}
			} catch (err) {
				if (!cancelled) setError(err);
			} finally {
				if (!cancelled) setLoading(false);
			}
		})();

		return () => {
			cancelled = true;
		};
	}, [primary.content_url, primary.size_bytes, retryKey]);

	if (loading) {
		return (
			<div
				aria-busy="true"
				className="flex h-full items-center justify-center bg-white text-neutral-500"
			>
				<Spinner size="lg" />
			</div>
		);
	}
	if (error || !view) {
		if (error instanceof ParseWorkbookError && error.code === "oversize") {
			return <UnviewableFile message={fallbackMessage(error, primary.filename)} />;
		}
		return (
			<div className="flex h-full flex-col items-center justify-center gap-3 bg-white p-6 text-center text-neutral-950">
				<div>
					<p className="text-sm font-medium">Couldn&apos;t open this spreadsheet</p>
					<p className="mt-1 text-xs text-neutral-500">
						{fallbackMessage(error, primary.filename)}
					</p>
				</div>
				<Button variant="secondary" size="sm" onClick={() => setRetryKey((key) => key + 1)}>
					Try again
				</Button>
			</div>
		);
	}

	const sheet = view.sheets[active] ?? view.sheets[0];

	return (
		<div className="flex h-full min-h-0 flex-col bg-white text-neutral-950">
			{view.sheets.length > 1 ? (
				<div
					role="tablist"
					aria-label="Worksheets"
					className="flex shrink-0 gap-1 overflow-x-auto border-neutral-200 border-b px-2 py-1.5"
				>
					{view.sheets.map((entry, index) => (
						<button
							key={entry.name}
							type="button"
							role="tab"
							aria-selected={index === active}
							className={
								index === active
									? "rounded-md bg-neutral-100 px-2.5 py-1 font-medium text-neutral-950 text-xs"
									: "rounded-md px-2.5 py-1 text-neutral-500 text-xs hover:bg-neutral-100"
							}
							onClick={() => setActive(index)}
						>
							{entry.name}
						</button>
					))}
				</div>
			) : null}

			{sheet.truncated ? (
				<p className="shrink-0 border-neutral-200 border-b px-3 py-1.5 text-neutral-500 text-xs">
					Showing the first {sheet.cells.length} rows. Download the file for the full workbook.
				</p>
			) : null}

			<div className="min-h-0 flex-1 overflow-hidden">
				<SpreadsheetGrid sheet={sheet} />
			</div>
		</div>
	);
}
