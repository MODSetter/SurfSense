"use client";
import type { Inputs } from "@/contracts/types/automation.types";

interface InputsSchemaPreviewProps {
	inputs: Inputs;
}

/**
 * Read-only JSON preview of an automation's accepted-inputs schema.
 * Most automations don't define inputs (defaults are baked into the
 * trigger's static_inputs), so the parent skips rendering this card
 * when ``inputs`` is null.
 */
export function InputsSchemaPreview({ inputs }: InputsSchemaPreviewProps) {
	return (
		<pre className="rounded-md bg-muted/40 px-3 py-2 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-words max-h-72">
			{JSON.stringify(inputs.schema, null, 2)}
		</pre>
	);
}
