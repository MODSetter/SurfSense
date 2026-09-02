function isEscaped(value: string, index: number): boolean {
	let precedingBackslashes = 0;
	for (let cursor = index - 1; cursor >= 0 && value[cursor] === "\\"; cursor -= 1) {
		precedingBackslashes += 1;
	}
	return precedingBackslashes % 2 === 1;
}

function hasBalancedLatexBraces(value: string): boolean {
	let depth = 0;
	for (let index = 0; index < value.length; index += 1) {
		if (isEscaped(value, index)) continue;
		if (value[index] === "{") depth += 1;
		if (value[index] === "}") depth -= 1;
		if (depth < 0) return false;
	}
	return depth === 0;
}

export type StudyTextSegment =
	| { type: "text"; value: string; offset: number }
	| { type: "math"; value: string; display: boolean; offset: number };

export function parseStudyText(value: string): StudyTextSegment[] | null {
	const segments: StudyTextSegment[] = [];
	let textStart = 0;
	let index = 0;
	while (index < value.length) {
		const delimiter = value.slice(index, index + 2);
		if ((delimiter === "\\)" || delimiter === "\\]") && !isEscaped(value, index)) {
			return null;
		}
		if ((delimiter !== "\\(" && delimiter !== "\\[") || isEscaped(value, index)) {
			index += 1;
			continue;
		}

		if (index > textStart) {
			segments.push({ type: "text", value: value.slice(textStart, index), offset: textStart });
		}
		const openingOffset = index;
		const display = delimiter === "\\[";
		const closing = display ? "\\]" : "\\)";
		const latexStart = index + 2;
		index = latexStart;
		while (index < value.length) {
			const candidate = value.slice(index, index + 2);
			if ((candidate === "\\(" || candidate === "\\[") && !isEscaped(value, index)) {
				return null;
			}
			if ((candidate === "\\)" || candidate === "\\]") && !isEscaped(value, index)) {
				if (candidate !== closing) return null;
				const latex = value.slice(latexStart, index);
				if (!latex.trim() || !hasBalancedLatexBraces(latex)) return null;
				segments.push({ type: "math", value: latex, display, offset: openingOffset });
				index += 2;
				textStart = index;
				break;
			}
			index += 1;
		}
		if (textStart !== index) return null;
	}
	if (textStart < value.length) {
		segments.push({ type: "text", value: value.slice(textStart), offset: textStart });
	}
	return segments;
}
