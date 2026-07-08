"use client";

import { Check, Copy, Download } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { downloadCsv, rowsToCsv } from "@/lib/playground/csv";

const MAX_TABLE_ROWS = 200;

function extractItems(data: unknown): Record<string, unknown>[] | null {
	if (
		typeof data === "object" &&
		data !== null &&
		"items" in data &&
		Array.isArray((data as { items: unknown }).items)
	) {
		const items = (data as { items: unknown[] }).items;
		if (items.every((item) => typeof item === "object" && item !== null)) {
			return items as Record<string, unknown>[];
		}
	}
	return null;
}

function cellText(value: unknown): string {
	if (value === null || value === undefined) return "";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
}

function ResultTable({ items }: { items: Record<string, unknown>[] }) {
	const columns = useMemo(() => {
		const keys = new Set<string>();
		for (const item of items.slice(0, MAX_TABLE_ROWS)) {
			for (const key of Object.keys(item)) keys.add(key);
		}
		return Array.from(keys);
	}, [items]);

	const rows = items.slice(0, MAX_TABLE_ROWS);

	return (
		<div className="overflow-x-auto rounded-md border border-border/60">
			<Table>
				<TableHeader>
					<TableRow>
						{columns.map((col) => (
							<TableHead key={col} className="whitespace-nowrap">
								{col}
							</TableHead>
						))}
					</TableRow>
				</TableHeader>
				<TableBody>
					{rows.map((item, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: rows have no stable id
						<TableRow key={i}>
							{columns.map((col) => (
								<TableCell key={col} className="max-w-xs truncate align-top text-xs">
									{cellText(item[col])}
								</TableCell>
							))}
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
}

export function OutputViewer({ data, filenameBase }: { data: unknown; filenameBase?: string }) {
	const items = useMemo(() => extractItems(data), [data]);
	const [view, setView] = useState<"table" | "json">(items ? "table" : "json");
	const [copied, setCopied] = useState(false);

	const json = useMemo(() => JSON.stringify(data, null, 2), [data]);

	const copy = () => {
		navigator.clipboard.writeText(json).then(() => {
			setCopied(true);
			setTimeout(() => setCopied(false), 1500);
		});
	};

	// Export the full item set (not just the display-capped rows) as CSV, with a
	// column per union key so nothing is dropped.
	const exportCsv = () => {
		if (!items || items.length === 0) return;
		const columns = Array.from(
			items.reduce((set, item) => {
				for (const key of Object.keys(item)) set.add(key);
				return set;
			}, new Set<string>())
		);
		downloadCsv(filenameBase ?? "output", rowsToCsv(items, columns));
	};

	const truncated = items && items.length > MAX_TABLE_ROWS;

	return (
		<div className="space-y-3">
			<div className="flex items-center justify-between">
				<Tabs value={view} onValueChange={(value) => setView(value as "table" | "json")}>
					<TabsList className="h-auto">
						{items && <TabsTrigger value="table">Table</TabsTrigger>}
						<TabsTrigger value="json">JSON</TabsTrigger>
					</TabsList>
				</Tabs>
				<div className="flex items-center gap-1">
					{items && items.length > 0 && (
						<Button
							type="button"
							variant="ghost"
							size="sm"
							onClick={exportCsv}
							className="gap-1.5"
						>
							<Download className="h-3.5 w-3.5" />
							Export CSV
						</Button>
					)}
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={copy}
						aria-label={copied ? "Copied JSON" : "Copy JSON"}
						className="h-8 w-8 p-0"
					>
						{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
					</Button>
				</div>
			</div>

			{items && items.length === 0 && (
				<p className="rounded-md border border-dashed border-border/60 px-4 py-6 text-center text-sm text-muted-foreground">
					No items returned.
				</p>
			)}

			{view === "table" && items && items.length > 0 ? (
				<>
					<ResultTable items={items} />
					{truncated && (
						<p className="text-xs text-muted-foreground">
							Showing first {MAX_TABLE_ROWS} of {items.length} items. Switch to JSON for the full
							output.
						</p>
					)}
				</>
			) : (
				<pre className="max-h-[480px] overflow-auto rounded-md border border-border/60 bg-muted/20 p-3 text-xs">
					<code>{json}</code>
				</pre>
			)}
		</div>
	);
}
