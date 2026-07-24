import { AppError } from "@/lib/error";

/** Map a 422 response's field failures to ``{ fieldName: message }`` for the form. */
export function fieldErrorsFromError(error: unknown): Record<string, string> {
	if (!(error instanceof AppError) || !error.fields) return {};
	const errors: Record<string, string> = {};
	for (const { loc, msg } of error.fields) {
		const name = topLevelField(loc);
		if (name && !errors[name]) errors[name] = msg;
	}
	return errors;
}

/** The input field a location path points at, dropping the ``body`` request root. */
function topLevelField(loc: string[]): string | undefined {
	const path = loc[0] === "body" ? loc.slice(1) : loc;
	return path[0];
}
