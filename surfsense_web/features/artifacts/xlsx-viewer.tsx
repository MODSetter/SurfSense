"use client";

import { useEffect, useState } from "react";
import { buildBackendUrl } from "@/lib/env-config";
import { cannotPreviewMessage } from "./file-format";
import {
	MAX_VIEWER_BYTES,
	ParseWorkbookError,
	type WorkbookView,
	parseWorkbook,
} from "./parse-workbook";
import { UnviewableArtifact } from "./unviewable-artifact";
import type { ArtifactFileViewerProps } from "./viewer-registry";

function columnLabel(index: number): string {
	let n = index;
	let label = "";
	while (n >= 0) {
		label = String.fromCharCode((n % 26) + 65) + label;
		n = Math.floor(n / 26) - 1;
	}
	return label;
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

export default function XlsxViewer({ primary }: ArtifactFileViewerProps) {
	const [view, setView] = useState<WorkbookView | null>(null);
	const [active, setActive] = useState(0);
	const [error, setError] = useState<unknown>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		let cancelled = false;
		setLoading(true);
		setError(null);
		setView(null);

		(async () => {
			try {
				if (primary.size_bytes > MAX_VIEWER_BYTES) {
					throw new ParseWorkbookError(
						"oversize",
						`Workbook is too large to preview (${primary.size_bytes} bytes)`,
					);
				}
				const response = await fetch(buildBackendUrl(primary.content_url));
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
	}, [primary.content_url, primary.size_bytes]);

	if (loading) {
		return (
			<div className="flex h-full items-center justify-center text-sm text-muted-foreground">
				Loading spreadsheet…
			</div>
		);
	}
	if (error || !view) {
		return <UnviewableArtifact message={fallbackMessage(error, primary.filename)} />;
	}

	const sheet = view.sheets[active] ?? view.sheets[0];
	const colCount = Math.max(1, ...sheet.cells.map((row) => row.length));

	return (
		<div className="flex h-full min-h-0 flex-col bg-background">
			{view.sheets.length > 1 ? (
				<div
					role="tablist"
					aria-label="Worksheets"
					className="flex shrink-0 gap-1 overflow-x-auto border-b px-2 py-1.5"
				>
					{view.sheets.map((entry, index) => (
						<button
							key={`${entry.name}-${index}`}
							type="button"
							role="tab"
							aria-selected={index === active}
							className={
								index === active
									? "rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-accent-foreground"
									: "rounded-md px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
							}
							onClick={() => setActive(index)}
						>
							{entry.name}
						</button>
					))}
				</div>
			) : null}

			{sheet.truncated ? (
				<p className="shrink-0 border-b px-3 py-1.5 text-xs text-muted-foreground">
					Showing the first {sheet.cells.length} rows. Download the file for the full
					workbook.
				</p>
			) : null}

			<div className="min-h-0 flex-1 overflow-auto">
				<table className="w-max min-w-full border-collapse text-xs">
					<thead>
						<tr>
							<th className="sticky left-0 top-0 z-20 border-b border-r bg-muted px-2 py-1 text-left font-medium text-muted-foreground" />
							{Array.from({ length: colCount }, (_, col) => (
								<th
									key={col}
									className="sticky top-0 z-10 border-b bg-muted px-2 py-1 text-center font-medium text-muted-foreground"
								>
									{columnLabel(col)}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						{sheet.cells.map((row, rowIndex) => (
							<tr
								key={rowIndex}
								className="[content-visibility:auto] [contain-intrinsic-size:0_28px]"
							>
								<th className="sticky left-0 z-10 border-r bg-muted px-2 py-1 text-right font-medium text-muted-foreground">
									{rowIndex + 1}
								</th>
								{Array.from({ length: colCount }, (_, col) => (
									<td
										key={col}
										className="max-w-64 truncate border-b border-r px-2 py-1 whitespace-pre"
										title={row[col]?.text || undefined}
									>
										{row[col]?.text ?? ""}
									</td>
								))}
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}
