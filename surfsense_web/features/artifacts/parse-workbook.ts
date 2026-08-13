import ExcelJS from "exceljs";
import * as SSF from "ssf";

/** Soft ceiling for in-browser grid rows per sheet (full file still downloads). */
export const MAX_DISPLAY_ROWS = 500;

/** Reject before ExcelJS allocates — keep below server artifact max (30 MiB). */
export const MAX_VIEWER_BYTES = 15 * 1024 * 1024;

export type ParseWorkbookErrorCode = "oversize" | "corrupt";

export class ParseWorkbookError extends Error {
	readonly code: ParseWorkbookErrorCode;

	constructor(code: ParseWorkbookErrorCode, message: string) {
		super(message);
		this.name = "ParseWorkbookError";
		this.code = code;
	}
}

export interface CellView {
	text: string;
}

export interface SheetView {
	name: string;
	cells: CellView[][];
	truncated: boolean;
}

export interface WorkbookView {
	sheets: SheetView[];
}

function cellText(cell: ExcelJS.Cell): string {
	const value = cell.value;
	if (value == null || value === "") return "";

	if (typeof value === "object" && value !== null && "richText" in value) {
		return (value as ExcelJS.CellRichTextValue).richText.map((part) => part.text).join("");
	}
	if (typeof value === "object" && value !== null && "text" in value && "hyperlink" in value) {
		return String((value as ExcelJS.CellHyperlinkValue).text ?? "");
	}
	if (typeof value === "object" && value !== null && "error" in value) {
		return String((value as ExcelJS.CellErrorValue).error);
	}
	if (typeof value === "object" && value !== null && "formula" in value) {
		const formula = value as ExcelJS.CellFormulaValue | ExcelJS.CellSharedFormulaValue;
		const result = "result" in formula ? formula.result : undefined;
		if (result == null || result === "") return "";
		return formatValue(result, cell.numFmt);
	}
	return formatValue(value, cell.numFmt);
}

function formatValue(value: ExcelJS.CellValue, numFmt: string | undefined): string {
	if (value instanceof Date) {
		try {
			return SSF.format(numFmt || "yyyy-mm-dd", excelSerialFromDate(value));
		} catch {
			return value.toISOString().slice(0, 10);
		}
	}
	if (typeof value === "number") {
		try {
			return SSF.format(numFmt || "General", value);
		} catch {
			return String(value);
		}
	}
	if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
	if (typeof value === "string") return value;
	return String(value ?? "");
}

function excelSerialFromDate(date: Date): number {
	// Excel serial day count (Windows epoch); good enough for display formatting.
	return date.getTime() / 86_400_000 + 25569;
}

function sheetMatrix(sheet: ExcelJS.Worksheet): { cells: CellView[][]; truncated: boolean } {
	const rowCount = sheet.rowCount || 0;
	const colCount = sheet.columnCount || 0;
	const displayRows = Math.min(rowCount, MAX_DISPLAY_ROWS);
	const cells: CellView[][] = [];
	for (let r = 1; r <= displayRows; r += 1) {
		const row: CellView[] = [];
		for (let c = 1; c <= colCount; c += 1) {
			row.push({ text: cellText(sheet.getCell(r, c)) });
		}
		cells.push(row);
	}
	return { cells, truncated: rowCount > MAX_DISPLAY_ROWS };
}

export async function parseWorkbook(data: ArrayBuffer): Promise<WorkbookView> {
	if (data.byteLength > MAX_VIEWER_BYTES) {
		throw new ParseWorkbookError(
			"oversize",
			`Workbook is ${(data.byteLength / (1024 * 1024)).toFixed(1)} MB; preview limit is ${
				MAX_VIEWER_BYTES / (1024 * 1024)
			} MB`,
		);
	}

	const workbook = new ExcelJS.Workbook();
	try {
		await workbook.xlsx.load(data);
	} catch {
		throw new ParseWorkbookError("corrupt", "This workbook could not be opened");
	}

	if (workbook.worksheets.length === 0) {
		throw new ParseWorkbookError("corrupt", "This workbook has no worksheets");
	}

	return {
		sheets: workbook.worksheets.map((sheet) => {
			const { cells, truncated } = sheetMatrix(sheet);
			return { name: sheet.name, cells, truncated };
		}),
	};
}
