/** CSV export helpers for the playground runs table and API output tables. */

function cellToString(value: unknown): string {
	if (value === null || value === undefined) return "";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
}

// Leading chars a spreadsheet treats as the start of a formula. Scraped API
// data is untrusted, so we neutralize these to prevent CSV injection.
const FORMULA_START = /^[=+@\t\r]/;
const LOOKS_NUMERIC = /^-?\d/;

function escapeCsvCell(value: unknown): string {
	let s = cellToString(value);
	if (FORMULA_START.test(s) || (s.startsWith("-") && !LOOKS_NUMERIC.test(s))) {
		s = `'${s}`;
	}
	if (/[",\n\r]/.test(s)) {
		s = `"${s.replace(/"/g, '""')}"`;
	}
	return s;
}

/**
 * Serialize rows to an RFC 4180 CSV string. Columns default to the union of
 * keys across all rows (stable insertion order); pass ``columns`` to fix the
 * order and subset.
 */
export function rowsToCsv(rows: Record<string, unknown>[], columns?: string[]): string {
	const cols =
		columns ??
		Array.from(
			rows.reduce((set, row) => {
				for (const key of Object.keys(row)) set.add(key);
				return set;
			}, new Set<string>())
		);
	const header = cols.map(escapeCsvCell).join(",");
	if (rows.length === 0) return header;
	const body = rows.map((row) => cols.map((col) => escapeCsvCell(row[col])).join(",")).join("\r\n");
	return `${header}\r\n${body}`;
}

/** Trigger a browser download of ``csv`` as ``{filenameBase}.csv`` (UTF-8, Excel-friendly). */
export function downloadCsv(filenameBase: string, csv: string): void {
	const safe = filenameBase.replace(/[^\w.-]+/g, "_") || "export";
	// Prepend a BOM so Excel detects UTF-8.
	const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = `${safe}.csv`;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}
